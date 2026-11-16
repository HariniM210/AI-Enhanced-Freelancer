import inspect, sys
sys.path.append('C:/Users/harin/OneDrive/Documents/AI-Enhanced-Freelancer')
from Backend.services import application_service as svc
print(inspect.signature(svc._complete_application))
print(inspect.signature(svc._run_completion_transaction))
