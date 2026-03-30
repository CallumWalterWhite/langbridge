import { NavLink } from "react-router-dom";

import { hasRuntimeAdminRole } from "../lib/runtimeAuthz";

const SETTINGS_SECTIONS = [
  {
    to: "/settings",
    label: "Runtime",
  },
  {
    to: "/settings/users",
    label: "Users",
    adminOnly: true,
  },
];

export function SettingsSectionNav({ session }) {
  const isAdmin = hasRuntimeAdminRole(session?.roles);
  const visibleSections = SETTINGS_SECTIONS.filter((section) => !section.adminOnly || isAdmin);

  return (
    <nav className="section-tabs settings-section-tabs" aria-label="Settings sections">
      {visibleSections.map((section) => (
        <NavLink
          key={section.to}
          to={section.to}
          end={section.to === "/settings"}
          className={({ isActive }) => `section-tab section-tab-link ${isActive ? "active" : ""}`.trim()}
        >
          {section.label}
        </NavLink>
      ))}
    </nav>
  );
}
