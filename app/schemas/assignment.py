from datetime import datetime
from pydantic import BaseModel, ConfigDict


class DoctorPatientAssignmentResponse(BaseModel):
    message: str
    doctor_id: int
    doctor_name: str
    patient_id: int
    patient_name: str
    assigned_at: datetime

    model_config = ConfigDict(from_attributes=True)
