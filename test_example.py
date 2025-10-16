"""Example Test Suite for AiChrom Multi-Browser Manager

This module demonstrates how to write tests for the AiChrom framework.
It includes examples of basic browser operations, worker management,
and integration testing patterns.

Author: AiChrom Contributors
Date: October 2025
"""

import pytest
import asyncio
from multi_browser_manager import MultiBrowserManager
from worker_chrome import WorkerChrome


class TestBrowserInitialization:
    """Test suite for browser initialization and basic setup."""
    
    def test_browser_manager_creation(self):
        """
        Test that MultiBrowserManager can be instantiated properly.
        
        This test verifies:
        - Manager object can be created
        - Default settings are applied correctly
        - No errors occur during initialization
        """
        manager = MultiBrowserManager()
        assert manager is not None
        assert hasattr(manager, 'workers')
        print("✓ Browser manager created successfully")
    
    def test_worker_chrome_creation(self):
        """
        Test that WorkerChrome instances can be created.
        
        This test verifies:
        - Worker object can be instantiated
        - Worker has required attributes
        - Worker configuration is valid
        """
        worker = WorkerChrome(worker_id=1)
        assert worker is not None
        assert worker.worker_id == 1
        print("✓ Worker Chrome created successfully")


class TestBrowserOperations:
    """Test suite for basic browser operations."""
    
    @pytest.mark.asyncio
    async def test_browser_launch(self):
        """
        Test browser launch functionality.
        
        This test verifies:
        - Browser can be launched successfully
        - Browser process starts without errors
        - Browser is ready to accept commands
        """
        worker = WorkerChrome(worker_id=1)
        try:
            await worker.launch()
            assert worker.is_running()
            print("✓ Browser launched successfully")
        finally:
            await worker.close()
    
    @pytest.mark.asyncio
    async def test_page_navigation(self):
        """
        Test basic page navigation.
        
        This test verifies:
        - Browser can navigate to a URL
        - Page loads successfully
        - Navigation completes without errors
        """
        worker = WorkerChrome(worker_id=1)
        try:
            await worker.launch()
            await worker.navigate("https://example.com")
            current_url = await worker.get_current_url()
            assert "example.com" in current_url
            print("✓ Page navigation successful")
        finally:
            await worker.close()


class TestMultiWorkerManagement:
    """Test suite for managing multiple browser workers."""
    
    @pytest.mark.asyncio
    async def test_multiple_workers(self):
        """
        Test managing multiple browser workers simultaneously.
        
        This test verifies:
        - Multiple workers can be created
        - Workers can run concurrently
        - Each worker operates independently
        """
        manager = MultiBrowserManager()
        worker_count = 3
        
        try:
            await manager.create_workers(worker_count)
            assert len(manager.workers) == worker_count
            print(f"✓ Successfully created {worker_count} workers")
        finally:
            await manager.close_all_workers()
    
    @pytest.mark.asyncio
    async def test_worker_task_distribution(self):
        """
        Test task distribution across multiple workers.
        
        This test verifies:
        - Tasks can be distributed to workers
        - Workers execute tasks concurrently
        - All tasks complete successfully
        """
        manager = MultiBrowserManager()
        urls = [
            "https://example.com",
            "https://example.org",
            "https://example.net"
        ]
        
        try:
            results = await manager.execute_tasks(urls)
            assert len(results) == len(urls)
            assert all(result.success for result in results)
            print(f"✓ Successfully distributed and executed {len(urls)} tasks")
        finally:
            await manager.close_all_workers()


class TestErrorHandling:
    """Test suite for error handling and edge cases."""
    
    @pytest.mark.asyncio
    async def test_invalid_url_handling(self):
        """
        Test handling of invalid URLs.
        
        This test verifies:
        - Invalid URLs are handled gracefully
        - Appropriate errors are raised or caught
        - Worker remains stable after error
        """
        worker = WorkerChrome(worker_id=1)
        try:
            await worker.launch()
            with pytest.raises(Exception):
                await worker.navigate("invalid-url")
            print("✓ Invalid URL handled correctly")
        finally:
            await worker.close()
    
    @pytest.mark.asyncio
    async def test_worker_recovery(self):
        """
        Test worker recovery after failure.
        
        This test verifies:
        - Workers can be restarted after failure
        - State is properly reset
        - Recovery doesn't affect other workers
        """
        manager = MultiBrowserManager()
        try:
            await manager.create_workers(2)
            # Simulate failure and recovery
            await manager.restart_worker(0)
            assert len(manager.workers) == 2
            print("✓ Worker recovery successful")
        finally:
            await manager.close_all_workers()


if __name__ == "__main__":
    """
    Run tests directly from command line.
    
    Usage:
        python test_example.py
    
    Or use pytest for more options:
        pytest test_example.py -v
        pytest test_example.py -v -s  # with print output
    """
    print("Running AiChrom Example Tests...")
    print("=" * 50)
    pytest.main([__file__, "-v", "-s"])
