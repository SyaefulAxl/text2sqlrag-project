"""
Resume Analyzer Service

Multi-step AI analysis chain for resume data extraction.
Uses GPT-4o-mini for structured extraction with textile domain expertise.

Ported from Resumes/main.py AIAnalyzer class and Resumes/config.py prompts.
"""

import json
import logging
import time
from typing import Dict, Any, Tuple, Optional

from openai import OpenAI, RateLimitError, APIError, BadRequestError

from app.config import settings

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════
# TEXTILE DOMAIN CONTEXT - WORLD-CLASS HR EXPERT
# ═══════════════════════════════════════════════════════════════════

TEXTILE_DOMAIN_CONTEXT = """
You are a WORLD-CLASS HR EXPERT specialized in the TEXTILE INDUSTRY with 20+ years 
of global experience across India, Bangladesh, Vietnam, Indonesia, Turkey, and Europe.

You have deep expertise in:

🏭 TEXTILE INDUSTRY SEGMENTS:
- Spinning: Ring Spinning, Open-End (Rotor), Air-Jet, Compact Spinning, Vortex
- Weaving: Shuttle Looms, Rapier, Air-Jet, Projectile, Water-Jet, Dobby, Jacquard
- Knitting: Circular (Single/Double Jersey), Flat Bed, Warp Knitting, Seamless
- Wet Processing: Dyeing (Yarn, Fabric, Garment), Printing, Finishing
- Garment: CMT (Cut-Make-Trim), FOB, Design, Merchandising
- Technical Textiles: Nonwovens, Geotextiles, Medical Textiles, Composites

🔧 MACHINE BRANDS & MODELS:
- Spinning: Rieter (G37, C80), Truetzschler (TC19i), LMW (LR9AX), Saurer (Autoconer), Murata (Vortex)
- Weaving: Picanol (OptiMax), Toyota (JAT810), Tsudakoma (ZAX-N), Dornier, Itema
- Knitting: Mayer & Cie (Relanit), Terrot, Pai Lung, Santoni, Stoll, Shima Seiki
- Processing: Benninger, Brückner, Monforts, Santex Rimar, Thies, Fong's

📊 KEY METRICS:
- Spinning: Count (Ne), TPI, Twist Multiplier, U%, CVm, IPI, Hairiness
- Weaving: Picks/cm, Reed Count, EPI, PPI, Loom Efficiency, Warp Breakage
- Quality: Uster Statistics, 4-point/10-point grading, AQL, GSM, Shrinkage
- Production: OEE (Overall Equipment Effectiveness), Yield, Waste%

💼 COMMON ROLES:
- Technical: Production Manager, Quality Head, Maintenance Head, Plant Manager
- Commercial: Sourcing Manager, Merchandiser, Business Development, Export Manager  
- Leadership: CEO, COO, VP Operations, Mill Director, General Manager
- Specialist: Lean Consultant, ERP Implementation, TPM Expert, Quality Auditor

🎓 RELEVANT CERTIFICATIONS:
- Industry: USTER Certification, ATIRA, SITRA, BTRA, TRA courses
- Quality: ISO 9001/14001 Lead Auditor, Six Sigma (Green/Black Belt)
- Production: TPM Practitioner, Lean Manufacturing, SMED, Kaizen
- ERP: SAP MM/PP, Oracle, MS Dynamics
"""

# ═══════════════════════════════════════════════════════════════════
# EXTRACTION PROMPTS
# ═══════════════════════════════════════════════════════════════════

STEP1_SYSTEM = """You are extracting PERSONAL DATA from a resume.
Return ONLY valid JSON with no extra text."""

STEP1_USER = """Extract personal information from this resume:

{resume_text}

Return JSON:
{{
    "name": "Full Name",
    "country_code": "+91 or +1 etc",
    "contact_number": "digits only",
    "email_id": "email@example.com",
    "age": "number or N/A",
    "current_location": "City, Country",
    "preferred_location_1": "City or Region preference 1",
    "preferred_location_2": "City or Region preference 2"
}}"""

STEP2_SYSTEM = f"""You are extracting EMPLOYMENT DATA from a resume.
{TEXTILE_DOMAIN_CONTEXT}
Return ONLY valid JSON with no extra text."""

STEP2_USER = """Extract employment information:

Resume:
{resume_text}

Previous data:
{context_data}

Return JSON:
{{
    "experience": "X years Y months",
    "current_organisation": "Company Name",
    "current_designation": "Job Title",
    "category": "Commercial or Non-Commercial",
    "department": ["Spinning", "Weaving", "etc"],
    "division": ["Cotton", "Synthetic", "etc"],
    "functions": ["Production", "Quality", "Maintenance", "etc"],
    "machines_brands": ["Rieter", "Toyota", "etc"],
    "machines_model": ["G35", "JAT810", "etc"],
    "skills": ["Spinning Technology", "Quality Control", "etc"],
    "raw_material_expertise": ["Cotton", "Polyester", "etc"],
    "plant_scale_capacity": "50,000 spindles or N/A",
    "plant_scale_capacity": "50,000 spindles or N/A",
    "languages_known": ["English", "Hindi", "etc"],
    
    "roles": ["Production Manager", "Shift Officer", "etc (extracted from work history)"],
    "primary_expertise": ["Spinning", "Quality", "etc (Top skill area)"],
    "secondary_expertise": ["Maintenance", "Manpower Handling", "etc"],
    
    "currency": "INR/USD/etc or N/A",
    "current_ctc": "Current salary amount or N/A",
    "expected_ctc": "Expected salary amount or N/A",
    "notice_period": "Notice period in days/months or N/A",
    "source": "Source mentioned in resume (e.g. LinkedIn, Referral) or N/A",
    "referred_by": "Name of referrer if mentioned or N/A"
}}"""

STEP3_SYSTEM = """You are extracting EDUCATION DATA from a resume.
Return ONLY valid JSON with no extra text."""

STEP3_USER = """Extract education information:

Resume:
{resume_text}

Previous data:
{context_data}

Return JSON:
{{
    "education_qualification": "B.Tech Textile Technology, MBA, etc",
    "specialization": "Spinning Technology or N/A",
    "certifications": ["ISO Auditor", "Six Sigma", "etc"]
}}"""

STEP4_SYSTEM = f"""You are a WORLD-CLASS SENIOR HR EVALUATOR for textile industry recruitment.
{TEXTILE_DOMAIN_CONTEXT}

You evaluate candidates with the precision of a top executive headhunter.
Return ONLY valid JSON with no extra text."""

STEP4_USER = """Based on the full resume and extracted data, provide your EXPERT HR evaluation.

Evaluate with the following criteria:
- Technical depth in textile processes
- Leadership and managerial experience
- Scale of operations handled (spindles, looms, employees)
- Industry reputation (worked at known mills)
- Career progression and stability
- Certifications and continuous learning

Resume:
{resume_text}

Extracted data:
{context_data}

Return JSON:
{{
    "summarize": "2-3 paragraph EXPERT summary covering: 1) Career trajectory and key achievements, 2) Technical expertise and specializations, 3) Leadership qualities and fit for senior roles. Be specific with numbers and machine names.",
    "vote": 1-5 (STRICT SCALE: 1=Entry-level/Poor fit, 2=Junior with potential, 3=Mid-level solid performer, 4=Senior expert, 5=Industry leader/Top talent),
    "consideration": "Specific next steps: Who should interview them? What role level suits them? Red flags to probe? Salary expectations based on experience?"
}}"""

MAX_RETRIES = 3
STEP_GAP_SECONDS = 1.0


class ResumeAnalyzerService:
    """
    Multi-step AI analysis for resume data extraction.
    
    Steps:
    1. Personal Data (name, contact, location)
    2. Employment Data (experience, skills, machines)
    3. Education Data (qualifications, certifications)
    4. HR Evaluation (summary, vote, consideration)
    """

    def __init__(self):
        """Initialize analyzer service."""
        self.client = OpenAI(api_key=settings.OPENAI_API_KEY)
        self.model = settings.RESUME_ANALYSIS_MODEL

    def analyze(
        self,
        resume_text: str,
        filename: str,
    ) -> Tuple[Optional[Dict[str, Any]], Dict[str, Any]]:
        """
        Run full 4-step analysis chain.
        
        Args:
            resume_text: Extracted text from resume
            filename: Original filename (for logging)
            
        Returns:
            Tuple of (extracted_data, stats)
        """
        start_time = time.time()
        
        stats = {
            "steps_completed": 0,
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
            "duration_seconds": 0.0,
            "cost_usd": 0.0,
            "error": None,
        }

        # Validation
        if len(resume_text) < 50:
            stats["error"] = "Resume text too short for analysis"
            return None, stats

        # Define steps
        steps = [
            ("Personal Data", STEP1_SYSTEM, STEP1_USER),
            ("Employment", STEP2_SYSTEM, STEP2_USER),
            ("Education", STEP3_SYSTEM, STEP3_USER),
            ("HR Evaluation", STEP4_SYSTEM, STEP4_USER),
        ]

        final_data = {}

        for i, (name, system_prompt, user_template) in enumerate(steps, 1):
            logger.info(f"  Step {i}: {name}...")

            # Build user prompt with context
            user_prompt = user_template.format(
                resume_text=resume_text[:8000],  # Limit text length
                context_data=json.dumps(final_data, ensure_ascii=False),
            )

            # Call AI
            step_data, usage = self._call_extractor(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                step_name=name,
                filename=filename,
            )

            if not step_data:
                stats["error"] = f"Failed at step {i}: {name}"
                return None, stats

            # Merge results
            final_data.update(step_data)
            stats["steps_completed"] = i

            # Track usage
            if usage:
                stats["prompt_tokens"] += usage.get("prompt_tokens", 0)
                stats["completion_tokens"] += usage.get("completion_tokens", 0)
                stats["total_tokens"] += usage.get("total_tokens", 0)

            # Delay between steps
            if i < len(steps):
                time.sleep(STEP_GAP_SECONDS)

        # Calculate final metrics
        stats["duration_seconds"] = round(time.time() - start_time, 3)
        stats["cost_usd"] = self._calculate_cost(
            stats["prompt_tokens"], 
            stats["completion_tokens"],
            self.model
        )
        
        logger.info(f"Analysis complete: {filename} ({stats['duration_seconds']}s, ${stats['cost_usd']:.4f})")
        return final_data, stats
    
    def _calculate_cost(self, input_tokens: int, output_tokens: int, model: str) -> float:
        """Calculate OpenAI API cost based on model."""
        # Pricing as of 2024 (per 1M tokens)
        pricing = {
            "gpt-4o-mini": {"input": 0.15, "output": 0.60},
            "gpt-4o": {"input": 2.50, "output": 10.00},
            "gpt-4": {"input": 30.00, "output": 60.00},
        }
        rates = pricing.get(model, pricing["gpt-4o-mini"])
        cost = (input_tokens * rates["input"] + output_tokens * rates["output"]) / 1_000_000
        return round(cost, 6)

    def _call_extractor(
        self,
        system_prompt: str,
        user_prompt: str,
        step_name: str,
        filename: str,
    ) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, int]]]:
        """Call AI for structured extraction."""
        for attempt in range(MAX_RETRIES):
            try:
                resp = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    response_format={"type": "json_object"},
                    temperature=0.2,
                    max_tokens=4000,
                    timeout=180.0,
                )

                content = (resp.choices[0].message.content or "").strip()
                
                # Parse JSON
                try:
                    parsed = json.loads(content)
                    if not isinstance(parsed, dict):
                        logger.warning(f"{step_name}: Response is not a dict")
                        continue
                except json.JSONDecodeError as e:
                    logger.warning(f"{step_name}: Invalid JSON - {e}")
                    continue

                # Extract usage
                usage = None
                if hasattr(resp, "usage") and resp.usage:
                    usage = {
                        "prompt_tokens": resp.usage.prompt_tokens or 0,
                        "completion_tokens": resp.usage.completion_tokens or 0,
                        "total_tokens": resp.usage.total_tokens or 0,
                    }

                return parsed, usage

            except BadRequestError as e:
                logger.error(f"{step_name}: BadRequest - {e}")
                return None, None

            except RateLimitError:
                wait = 2 ** attempt
                logger.warning(f"{step_name}: Rate limited, waiting {wait}s")
                time.sleep(wait)

            except APIError as e:
                if hasattr(e, "status_code") and 500 <= e.status_code < 600:
                    wait = 2 ** attempt
                    logger.warning(f"{step_name}: Server error, waiting {wait}s")
                    time.sleep(wait)
                else:
                    logger.error(f"{step_name}: API error - {e}")
                    return None, None

            except Exception as e:
                logger.error(f"{step_name}: Unexpected error - {e}")
                if attempt < MAX_RETRIES - 1:
                    time.sleep(STEP_GAP_SECONDS)

        logger.error(f"{step_name}: All retries failed for {filename}")
        return None, None
