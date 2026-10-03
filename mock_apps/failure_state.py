from pydantic import BaseModel

class FailureConfig(BaseModel):
    flaky_submit_once: bool = False
    strict_date_validation: bool = True
    duplicate_existing: bool = False
    slow_page: bool = False
    has_flaked: bool = False

# Global state singleton for mock apps
failure_config = FailureConfig()

def reset_failure_config():
    global failure_config
    failure_config = FailureConfig()
