import json
import os
from typing import Any

import requests
from dotenv import load_dotenv

load_dotenv()


class MageAPIClient:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(MageAPIClient, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self.base_url = os.getenv('BASE_URL', 'http://localhost:6789')
        self.oauth_token = os.getenv('OAUTH_TOKEN')
        self.api_key = os.getenv('API_KEY')
        self.project_name = os.getenv('PROJECT_NAME', 'default_repo')
        self._initialized = True

    def _get_headers(self) -> dict[str, str]:
        headers = {
            'Content-Type': 'application/json',
            'X-API-KEY': self.api_key,
        }
        if self.oauth_token:
            headers['Cookie'] = f'oauth_token={self.oauth_token}'
        return headers

    def pipeline_exists(self, pipeline_uuid: str) -> bool:
        """Check if a pipeline exists."""
        try:
            url = f'{self.base_url}/api/pipelines/{pipeline_uuid}'
            response = requests.get(url, headers=self._get_headers(), timeout=10)

            if response.status_code == 200:
                data = response.json()
                if "error" in data:
                    return False
                return True
            return False
        except Exception as e:
            print(f"Error checking pipeline existence: {e}")
            return False

    def create_pipeline(self, pipeline_uuid: str, pipeline_type: str = "python") -> dict[str, Any] | None:
        """Create a new pipeline."""
        payload = {
            "pipeline": {
                "name": pipeline_uuid,
                "type": pipeline_type
            }
        }

        try:
            url = f'{self.base_url}/api/pipelines'
            response = requests.post(url, headers=self._get_headers(), json=payload, timeout=10)

            if response.status_code == 200:
                data = response.json()
                if "error" in data:
                    print("❌ Failed to create pipeline.")
                    print(f"Response: {json.dumps(data, indent=2)}")
                    return None
                print(f"✅ Pipeline '{pipeline_uuid}' created successfully!")
                return data
            else:
                print(f"❌ Failed to create pipeline. Status: {response.status_code}")
                print(f"Response: {response.text}")
                return None
        except Exception as e:
            print(f"❌ Error creating pipeline: {e}")
            return None

    def block_exists(self, pipeline_uuid: str, block_uuid: str) -> bool:
        """Check if a block exists in a pipeline."""
        try:
            url = f'{self.base_url}/api/pipelines/{pipeline_uuid}/blocks/{block_uuid}'
            response = requests.get(url, headers=self._get_headers(), timeout=10)

            if response.status_code == 200:
                data = response.json()
                if "error" in data:
                    return False
                return "block" in data and data["block"] is not None
            return False
        except Exception as e:
            print(f"Error checking block existence: {e}")
            return False

    def create_block(self, pipeline_uuid: str, block_name: str, block_content: str,
                    block_type: str = "data_loader") -> dict[str, Any] | None:
        """Create a new block in a pipeline."""
        payload = {
            "block": {
                "name": block_name,
                "type": block_type,
                "language": "python",
                "content": block_content,
                "priority": 0,
                "configuration": {
                    "data_source": None
                }
            },
            "api_key": self.api_key
        }

        try:
            url = f'{self.base_url}/api/pipelines/{pipeline_uuid}/blocks'
            response = requests.post(url, headers=self._get_headers(), json=payload, timeout=15)

            if response.status_code in [200, 201]:
                data = response.json()
                if "error" in data:
                    print("❌ Failed to create block.")
                    print(f"Response: {json.dumps(data, indent=2)}")
                    return None
                print(f"✅ Block '{block_name}' created successfully!")
                return data
            else:
                print(f"❌ Failed to create block. Status: {response.status_code}")
                print(f"Response: {response.text}")
                return None
        except Exception as e:
            print(f"❌ Error creating block: {e}")
            return None

    def get_pipeline_schedules(self, pipeline_uuid: str) -> list:
        """Get all pipeline schedules/triggers."""
        url = f"{self.base_url}/api/pipelines/{pipeline_uuid}/pipeline_schedules"
        try:
            response = requests.get(
                url,
                headers=self._get_headers(),
                timeout=15
            )
            response.raise_for_status()
            return response.json().get("pipeline_schedules", [])
        except Exception as e:
            print(f"Error fetching schedules: {e}")
            return []

    def create_api_trigger(self, pipeline_uuid: str, trigger_name: str) -> dict[str, Any] | None:
        """Create an API trigger for a pipeline (only once)."""
        url = f"{self.base_url}/api/pipelines/{pipeline_uuid}/pipeline_schedules?project={self.project_name}"

        payload = {
            "pipeline_schedule": {
                "name": trigger_name,
                "schedule_type": "api",
                "status": "active"
            }
        }

        try:
            response = requests.post(url, headers=self._get_headers(), json=payload, timeout=15)
            data = response.json()

            if "error" in data:
                print("❌ Mage returned an error during trigger creation")
                print(json.dumps(data, indent=2))
                return None

            schedule = data.get("pipeline_schedule")
            if schedule and schedule.get("id") and schedule.get("token"):
                print(f"✅ API Trigger '{trigger_name}' created successfully!")
                return schedule
            else:
                print("❌ Trigger creation failed")
                print(json.dumps(data, indent=2))
                return None
        except Exception as e:
            print(f"❌ Error creating API trigger: {e}")
            return None

    def trigger_pipeline(self, schedule_id: int, trigger_token: str,
                        run_variables: dict[str, Any] | None = None) -> dict[str, Any] | None:
        """Trigger a pipeline execution (creates a new run)."""
        url = f"{self.base_url}/api/pipeline_schedules/{schedule_id}/pipeline_runs/{trigger_token}"

        payload = {}
        if run_variables:
            payload["pipeline_run"] = {
                "variables": run_variables
            }

        try:
            response = requests.post(url, headers=self._get_headers(), json=payload, timeout=15)
            response.raise_for_status()

            data = response.json()
            if "error" in data:
                print("❌ Mage returned an error during execution")
                print(json.dumps(data, indent=2))
                return None

            print("✅ Pipeline run created successfully!")
            return data
        except Exception as e:
            print(f"❌ Error triggering pipeline: {e}")
            return None


class PipelineOrchestrator:

    # Configuration from environment
    PIPELINE_UUID = os.getenv('MAGE_PIPELINE_UUID', 'process_pdf_batch')
    TRIGGER_NAME = os.getenv('MAGE_TRIGGER_NAME', 'batch_runner_trigger')
    BLOCK_NAME = "process_pdfs_batch_loader"

    def __init__(self):
        self.client = MageAPIClient()
        self.schedule_id = None
        self.trigger_token = None
        self._initialized = False

    def _get_block_content(self) -> str:
        """Returns the block content for batch PDF processing with shared model loading."""
        return '''if 'data_loader' not in globals():
    from mage_ai.data_preparation.decorators import data_loader

@data_loader
def process_pdfs_batch_loader(*args, **kwargs):
    """
    Process multiple PDFs for a single knowledge document.
    Models are loaded once and reused for all files.
    """
    from th2rag.rag.tasks.process_pdf import process_pdfs_background
    
    # Get parameters
    sources = kwargs.get("sources")  # List of S3 URLs
    doc_id = kwargs.get("doc_id")
    
    print(f"doc_id = {doc_id}")
    print(f"sources = {sources}")
    print(f"Processing {len(sources) if sources else 0} file(s)")
    
    if not sources or not doc_id:
        raise ValueError(f"Missing required parameters. doc_id: {doc_id}, sources: {sources}")
    
    if not isinstance(sources, list):
        raise ValueError(f"sources must be a list, got {type(sources)}")
    
    # Call the batch background processor
    # This function loads models ONCE and processes all files
    result = process_pdfs_background(doc_id=int(doc_id), sources=sources)
    
    return {
        "status": "completed", 
        "doc_id": doc_id, 
        "total_files": len(sources),
        "result": result
    }
'''

    def _ensure_pipeline_exists(self) -> bool:
        """Ensure pipeline exists, create if it doesn't."""
        print(f"\n[1/4] Checking if pipeline '{self.PIPELINE_UUID}' exists...")

        if not self.client.pipeline_exists(self.PIPELINE_UUID):
            print(f"   Pipeline not found. Creating '{self.PIPELINE_UUID}'...")
            result = self.client.create_pipeline(self.PIPELINE_UUID)
            if not result:
                print("❌ Failed to create pipeline. Aborting.")
                return False
        else:
            print(f"   ✓ Pipeline '{self.PIPELINE_UUID}' already exists.")

        return True

    def _ensure_block_exists(self) -> bool:
        """Ensure block exists, create if it doesn't."""
        print(f"\n[2/4] Checking if block '{self.BLOCK_NAME}' exists...")

        if not self.client.block_exists(self.PIPELINE_UUID, self.BLOCK_NAME):
            print(f"   Block not found. Creating '{self.BLOCK_NAME}'...")
            block_content = self._get_block_content()
            result = self.client.create_block(
                self.PIPELINE_UUID,
                self.BLOCK_NAME,
                block_content
            )
            if not result:
                print("❌ Failed to create block. Aborting.")
                return False
        else:
            print(f"   ✓ Block '{self.BLOCK_NAME}' already exists.")

        return True

    def _load_or_create_trigger(self) -> bool:
        """Load existing trigger or create if it doesn't exist (ONCE ONLY)."""
        print(f"\n[3/4] Checking for API trigger '{self.TRIGGER_NAME}'...")

        # Check if trigger already exists
        schedules = self.client.get_pipeline_schedules(self.PIPELINE_UUID)
        existing_trigger = next(
            (s for s in schedules if s.get("name") == self.TRIGGER_NAME),
            None
        )

        if existing_trigger:
            self.schedule_id = existing_trigger.get("id")
            self.trigger_token = existing_trigger.get("token")
            print(f"   ✓ Trigger '{self.TRIGGER_NAME}' already exists.")
            print(f"   Schedule ID: {self.schedule_id}")
            print(f"   Trigger Token: {self.trigger_token}")
            return True

        # Create trigger if it doesn't exist
        print(f"   Trigger not found. Creating '{self.TRIGGER_NAME}'...")
        trigger_info = self.client.create_api_trigger(self.PIPELINE_UUID, self.TRIGGER_NAME)
        if not trigger_info:
            print("❌ Failed to create API trigger. Aborting.")
            return False

        self.schedule_id = trigger_info.get("id")
        self.trigger_token = trigger_info.get("token")

        print(f"   Schedule ID: {self.schedule_id}")
        print(f"   Trigger Token: {self.trigger_token}")

        return True

    def initialize(self) -> bool:
        """Initialize pipeline infrastructure (call once at startup)."""
        if self._initialized:
            return True

        print("=" * 70)
        print("INITIALIZING MAGE PIPELINE INFRASTRUCTURE")
        print("=" * 70)

        # Step 1: Ensure pipeline exists
        if not self._ensure_pipeline_exists():
            return False

        # Step 2: Ensure block exists
        if not self._ensure_block_exists():
            return False

        # Step 3: Load or create trigger (ONCE)
        if not self._load_or_create_trigger():
            return False

        self._initialized = True
        print("\n✅ Pipeline infrastructure initialized successfully!")
        print("=" * 70)
        return True

    def execute_batch_upload(self, doc_id: str, sources: list[str]) -> dict[str, Any] | None:
        """
        Execute pipeline for batch PDF processing.
        This creates a SINGLE RUN that processes ALL files with shared model loading.
        
        Args:
            doc_id: Document ID
            sources: List of S3 URLs to process
        
        Returns:
            Execution result or None if failed
        """
        # Ensure infrastructure is initialized
        if not self._initialized:
            if not self.initialize():
                return None

        print("\n" + "=" * 70)
        print(f"CREATING BATCH PIPELINE RUN - {len(sources)} FILES")
        print("=" * 70)

        # Create a single run with all sources
        print("\n[4/4] Creating pipeline run for batch processing...")
        print(f"   doc_id: {doc_id}")
        print(f"   sources: {len(sources)} file(s)")
        for idx, source in enumerate(sources, 1):
            print(f"      [{idx}] {source}")

        run_variables = {
            "doc_id": doc_id,
            "sources": sources  # Pass entire list as a single variable
        }

        execution_result = self.client.trigger_pipeline(
            self.schedule_id,
            self.trigger_token,
            run_variables
        )

        if execution_result:
            print("\n" + "=" * 70)
            print("BATCH PIPELINE RUN STARTED")
            print("=" * 70)
            print(f"Schedule ID    : {self.schedule_id}")
            print(f"Trigger Token  : {self.trigger_token}")
            print(f"Doc ID         : {doc_id}")
            print(f"Total Files    : {len(sources)}")

            run_info = execution_result.get('pipeline_run', {})
            run_id = run_info.get('id')
            status = run_info.get('status')

            if run_id:
                print(f"Run ID         : {run_id}")
                print(f"Status         : {status}")
                print(f"\nView in Mage: {self.client.base_url}/pipelines/{self.PIPELINE_UUID}/runs/{run_id}")

            print("=" * 70)

            return {
                "run_id": run_id,
                "status": status,
                "doc_id": doc_id,
                "total_files": len(sources),
                "sources": sources
            }
        else:
            print("❌ Failed to create pipeline run.")
            return None


# Global orchestrator instance (singleton pattern)
_orchestrator_instance = None

def get_orchestrator() -> PipelineOrchestrator:
    """Get or create the global orchestrator instance."""
    global _orchestrator_instance
    if _orchestrator_instance is None:
        _orchestrator_instance = PipelineOrchestrator()
        _orchestrator_instance.initialize()
    return _orchestrator_instance


def process_knowledge_upload_batch(doc_id: str, sources: list[str]) -> dict[str, Any] | None:
    """
    Process a knowledge upload with multiple files in a single batch.
    Models are loaded once and reused for all files.
    
    Args:
        doc_id: Document ID
        sources: List of S3 URLs to process
    
    Returns:
        Execution result or None if failed
    """
    orchestrator = get_orchestrator()
    return orchestrator.execute_batch_upload(doc_id, sources)


def main():
    """Main entry point - simulates batch knowledge uploads."""
    print("\n" + "=" * 70)
    print("MAGE PDF BATCH PROCESSOR - KNOWLEDGE UPLOAD HANDLER")
    print("=" * 70)

    # Initialize once
    orchestrator = get_orchestrator()

    # Simulate batch uploads
    while True:
        print("\n" + "-" * 70)
        doc_id = input("\nEnter Document ID (or 'q' to quit): ").strip()

        if doc_id.lower() == 'q':
            break

        num_files = input("How many files? ").strip()

        try:
            num_files = int(num_files)
        except ValueError:
            print("\n❌ Error: Number of files must be an integer.")
            continue

        sources = []
        for i in range(num_files):
            source = input(f"Enter Source URL #{i+1}: ").strip()
            if source:
                sources.append(source)

        if not all([doc_id, sources]):
            print("\n❌ Error: Document ID and at least one Source are required.")
            continue

        # Process batch upload - creates ONE RUN for all files
        result = process_knowledge_upload_batch(doc_id, sources)

        if result:
            print(f"\n✅ Batch upload processed! Run ID: {result['run_id']}")
            print(f"   Processing {result['total_files']} file(s)")
        else:
            print("\n❌ Upload failed. Check the errors above.")


if __name__ == "__main__":
    main()
