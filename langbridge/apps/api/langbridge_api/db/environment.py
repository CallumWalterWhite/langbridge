from sqlalchemy import String, Column, ForeignKey, UUID
from sqlalchemy.orm import Mapped, relationship

from .auth import Organization

from .base import Base

class OrganisationEnvironmentSetting(Base):
    __tablename__ = "organisation_environment_settings"

    id = Column(UUID(as_uuid=True), primary_key=True)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    setting_key = Column(String(255), nullable=False)
    setting_value = Column(String(1024), nullable=False)

    organization: Mapped["Organization"] = relationship("Organization", back_populates="environment_settings")
