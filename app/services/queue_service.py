"""
Resume Processing Queue Service

Implements a semaphore-based queue for concurrent request limiting.
Ensures max N resumes are processed simultaneously.
"""

import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Any, Callable, List, Optional
from enum import Enum

from app.config import settings

logger = logging.getLogger(__name__)


class QueueStatus(str, Enum):
    """Status of a queued item."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class QueueItem:
    """A single item in the processing queue."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = field(default_factory=datetime.now)
    status: QueueStatus = QueueStatus.PENDING
    position: int = 0
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class ResumeProcessingQueue:
    """
    Async queue for resume processing with concurrency limiting.
    
    Uses asyncio.Semaphore to limit concurrent processing.
    Tracks queue position and status for each request.
    """

    def __init__(self, max_concurrent: int = None):
        """
        Initialize queue.
        
        Args:
            max_concurrent: Maximum concurrent processing tasks (default from config)
        """
        self.max_concurrent = max_concurrent or settings.RESUME_MAX_CONCURRENT
        self.semaphore = asyncio.Semaphore(self.max_concurrent)
        self.queue: Dict[str, QueueItem] = {}
        self.processing_count = 0
        self.total_processed = 0
        self._lock = asyncio.Lock()

    async def submit(
        self,
        process_fn: Callable,
        *args,
        **kwargs
    ) -> QueueItem:
        """
        Submit a task to the queue.
        
        Args:
            process_fn: The processing function to call
            *args, **kwargs: Arguments to pass to the function
            
        Returns:
            QueueItem with initial status
        """
        async with self._lock:
            item = QueueItem()
            item.position = len([q for q in self.queue.values() if q.status == QueueStatus.PENDING])
            self.queue[item.id] = item
            
            logger.info(f"Queue: Added {item.id}, position {item.position + 1}")
        
        # Process in background
        asyncio.create_task(self._process(item, process_fn, *args, **kwargs))
        
        return item

    async def _process(
        self,
        item: QueueItem,
        process_fn: Callable,
        *args,
        **kwargs
    ) -> None:
        """Process item with semaphore limiting."""
        try:
            # Wait for semaphore slot
            async with self.semaphore:
                async with self._lock:
                    item.status = QueueStatus.PROCESSING
                    self.processing_count += 1
                    
                    # Update positions for pending items
                    for q in self.queue.values():
                        if q.status == QueueStatus.PENDING and q.position > 0:
                            q.position -= 1
                
                logger.info(f"Queue: Processing {item.id}")
                
                # Run the actual processing
                if asyncio.iscoroutinefunction(process_fn):
                    result = await process_fn(*args, **kwargs)
                else:
                    # Run sync function in executor
                    loop = asyncio.get_event_loop()
                    result = await loop.run_in_executor(None, lambda: process_fn(*args, **kwargs))
                
                item.result = result
                item.status = QueueStatus.COMPLETED
                
        except Exception as e:
            logger.error(f"Queue: Failed {item.id}: {e}")
            item.status = QueueStatus.FAILED
            item.error = str(e)
            
        finally:
            async with self._lock:
                self.processing_count -= 1
                self.total_processed += 1

    def get_status(self, item_id: str) -> Optional[QueueItem]:
        """Get status of a queued item."""
        return self.queue.get(item_id)

    def get_queue_info(self) -> Dict[str, Any]:
        """Get overall queue status."""
        pending = len([q for q in self.queue.values() if q.status == QueueStatus.PENDING])
        processing = len([q for q in self.queue.values() if q.status == QueueStatus.PROCESSING])
        
        return {
            "max_concurrent": self.max_concurrent,
            "currently_processing": processing,
            "pending": pending,
            "total_processed": self.total_processed,
            "queue_length": pending + processing,
        }

    def cleanup_completed(self, max_age_seconds: int = 3600) -> int:
        """Remove completed items older than max_age."""
        now = datetime.now()
        to_remove = []
        
        for item_id, item in self.queue.items():
            if item.status in (QueueStatus.COMPLETED, QueueStatus.FAILED):
                age = (now - item.created_at).total_seconds()
                if age > max_age_seconds:
                    to_remove.append(item_id)
        
        for item_id in to_remove:
            del self.queue[item_id]
            
        return len(to_remove)


# Singleton instance
_queue = None

def get_processing_queue() -> ResumeProcessingQueue:
    """Get singleton instance of ResumeProcessingQueue."""
    global _queue
    if _queue is None:
        _queue = ResumeProcessingQueue()
    return _queue
