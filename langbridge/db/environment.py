from sqlalchemy import String, Table, Column, ForeignKey, Boolean, UUID, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base
from .auth import Organization

class OrganisationEnvironmentSetting(Base):
    __tablename__ = "organisation_environment_settings"

    id = Column(UUID(as_uuid=True), primary_key=True)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    setting_key = Column(String(255), nullable=False)
    setting_value = Column(String(1024), nullable=False)

    organization: Mapped["Organization"] = relationship("Organization", back_populates="projects")