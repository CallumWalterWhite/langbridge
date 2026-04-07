import { useEffect, useMemo, useRef, useState } from "react";

export function DashboardBuilderFieldSelect({
  fields,
  value,
  onChange,
  placeholder = "Select field",
  allowEmpty = false,
  emptyLabel = "None",
  filterKinds = null,
}) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const containerRef = useRef(null);

  const filtered = useMemo(() => {
    const normalizedQuery = String(query || "").trim().toLowerCase();
    return (Array.isArray(fields) ? fields : []).filter((field) => {
      if (Array.isArray(filterKinds) && filterKinds.length > 0 && !filterKinds.includes(field.kind)) {
        return false;
      }
      if (!normalizedQuery) {
        return true;
      }
      const haystack = [field.label, field.id, field.tableKey || "", field.kind || ""]
        .filter(Boolean)
        .join(" ")
        .toLowerCase();
      return haystack.includes(normalizedQuery);
    });
  }, [fields, filterKinds, query]);

  const selectedField = (Array.isArray(fields) ? fields : []).find((field) => field.id === value) || null;

  useEffect(() => {
    if (!open) {
      setQuery("");
      return;
    }

    function handleClick(event) {
      if (!containerRef.current) {
        return;
      }
      if (!containerRef.current.contains(event.target)) {
        setOpen(false);
      }
    }

    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, [open]);

  return (
    <div className="field-select" ref={containerRef}>
      <button
        className="select-input field-select-trigger"
        type="button"
        onClick={() => setOpen((current) => !current)}
      >
        <span className="field-select-copy">
          <strong>
            {selectedField?.label || (allowEmpty && value === "" ? emptyLabel : placeholder)}
          </strong>
          {selectedField?.tableKey ? <small>{selectedField.tableKey}</small> : null}
        </span>
        <span className="field-select-caret">{open ? "Close" : "Select"}</span>
      </button>

      {open ? (
        <div className="field-select-popover">
          <div className="field-select-search">
            <input
              className="text-input"
              type="search"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search fields"
            />
          </div>

          <div className="field-select-list">
            {allowEmpty ? (
              <button
                className={`field-select-option ${value === "" ? "active" : ""}`.trim()}
                type="button"
                onMouseDown={(event) => event.preventDefault()}
                onClick={() => {
                  onChange("");
                  setOpen(false);
                }}
              >
                <strong>{emptyLabel}</strong>
              </button>
            ) : null}

            {filtered.map((field) => (
              <button
                key={field.id}
                className={`field-select-option ${field.id === value ? "active" : ""}`.trim()}
                type="button"
                onMouseDown={(event) => event.preventDefault()}
                onClick={() => {
                  onChange(field.id);
                  setOpen(false);
                }}
              >
                <strong>{field.label}</strong>
                <small>{field.tableKey || field.kind}</small>
              </button>
            ))}

            {filtered.length === 0 ? (
              <div className="field-select-empty">No fields found.</div>
            ) : null}
          </div>
        </div>
      ) : null}
    </div>
  );
}
