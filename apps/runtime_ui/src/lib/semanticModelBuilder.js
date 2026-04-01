import { createLocalId } from "./runtimeUi";

export const SEMANTIC_DIMENSION_TYPES = [
  "string",
  "integer",
  "number",
  "boolean",
  "date",
  "time",
];

export const SEMANTIC_MEASURE_TYPES = ["number", "integer", "boolean", "date", "time", "string"];

export const SEMANTIC_MEASURE_AGGREGATIONS = [
  "sum",
  "avg",
  "count",
  "count_distinct",
  "min",
  "max",
];

export const SEMANTIC_RELATIONSHIP_TYPES = [
  "many_to_one",
  "one_to_many",
  "one_to_one",
  "many_to_many",
  "left",
  "inner",
];

function readDatasetMap(model) {
  if (model?.datasets && typeof model.datasets === "object") {
    return model.datasets;
  }
  if (model?.tables && typeof model.tables === "object") {
    return model.tables;
  }
  return {};
}

function buildDimensionField(field = {}) {
  return {
    id: createLocalId("semantic-dimension"),
    name: String(field.name || "").trim(),
    expression: String(field.expression || "").trim(),
    type: String(field.type || "string").trim() || "string",
    primaryKey: Boolean(field.primary_key ?? field.primaryKey),
  };
}

function buildMeasureField(field = {}) {
  return {
    id: createLocalId("semantic-measure"),
    name: String(field.name || "").trim(),
    expression: String(field.expression || "").trim(),
    type: String(field.type || "number").trim() || "number",
    aggregation: String(field.aggregation || "sum").trim() || "sum",
  };
}

function buildRelationship(relationship = {}) {
  let sourceDataset = String(
    relationship.source_dataset || relationship.sourceDataset || relationship.from || relationship.from_ || "",
  ).trim();
  let sourceField = String(relationship.source_field || relationship.sourceField || "").trim();
  let targetDataset = String(
    relationship.target_dataset || relationship.targetDataset || relationship.to || "",
  ).trim();
  let targetField = String(relationship.target_field || relationship.targetField || "").trim();

  const joinExpression = String(relationship.join_on || relationship.on || "").trim();
  if ((!sourceField || !targetField) && joinExpression.includes("=")) {
    const [left, right] = joinExpression.split("=").map((item) => item.trim());
    const [leftDataset, leftField] = left.split(".");
    const [rightDataset, rightField] = right.split(".");
    sourceDataset ||= String(leftDataset || "").trim();
    sourceField ||= String(leftField || "").trim();
    targetDataset ||= String(rightDataset || "").trim();
    targetField ||= String(rightField || "").trim();
  }

  return {
    id: createLocalId("semantic-relationship"),
    name: String(relationship.name || "").trim(),
    sourceDataset,
    sourceField,
    targetDataset,
    targetField,
    type: String(relationship.type || "many_to_one").trim() || "many_to_one",
  };
}

export function sanitizeSemanticKey(value) {
  return String(value || "")
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9_]+/g, "_")
    .replace(/^_+|_+$/g, "");
}

export function normalizeSemanticFieldType(value, { preferMeasure = false } = {}) {
  const raw = String(value || "").trim().toLowerCase();
  if (!raw) {
    return preferMeasure ? "number" : "string";
  }
  if (raw.includes("bool")) {
    return "boolean";
  }
  if (raw.includes("date") || raw.includes("time")) {
    return raw.includes("date") && !raw.includes("time") ? "date" : "time";
  }
  if (raw.includes("int")) {
    return "integer";
  }
  if (
    raw.includes("decimal") ||
    raw.includes("numeric") ||
    raw.includes("number") ||
    raw.includes("float") ||
    raw.includes("double") ||
    raw.includes("real") ||
    raw.includes("money")
  ) {
    return "number";
  }
  return preferMeasure ? "number" : "string";
}

function inferPrimaryKey(columnName, datasetName) {
  const datasetRoot = String(datasetName || "")
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]/g, "");
  const normalizedColumn = String(columnName || "").trim().toLowerCase();
  return (
    normalizedColumn === "id" ||
    normalizedColumn === `${datasetRoot}id` ||
    normalizedColumn === `${datasetRoot}_id`
  );
}

function uniqueSemanticKey(value, existingKeys) {
  const root = sanitizeSemanticKey(value) || "dataset";
  let nextValue = root;
  let counter = 2;
  const normalizedExisting = new Set(
    (Array.isArray(existingKeys) ? existingKeys : [])
      .map((item) => sanitizeSemanticKey(item))
      .filter(Boolean),
  );
  while (normalizedExisting.has(nextValue)) {
    nextValue = `${root}_${counter}`;
    counter += 1;
  }
  return nextValue;
}

function findDatasetOption(datasetOptions, semanticKey, relationName) {
  const options = Array.isArray(datasetOptions) ? datasetOptions : [];
  const normalizedKey = String(semanticKey || "").trim().toLowerCase();
  const normalizedRelation = String(relationName || "").trim().toLowerCase();
  return (
    options.find((item) => String(item?.name || "").trim().toLowerCase() === normalizedKey) ||
    options.find((item) => String(item?.sql_alias || "").trim().toLowerCase() === normalizedRelation) ||
    options.find((item) => String(item?.name || "").trim().toLowerCase() === normalizedRelation) ||
    null
  );
}

export function createEmptySemanticDimension() {
  return {
    id: createLocalId("semantic-dimension"),
    name: "",
    expression: "",
    type: "string",
    primaryKey: false,
  };
}

export function createEmptySemanticMeasure() {
  return {
    id: createLocalId("semantic-measure"),
    name: "",
    expression: "",
    type: "number",
    aggregation: "sum",
  };
}

export function createEmptySemanticRelationship(datasetKeys = []) {
  const [firstKey = "", secondKey = ""] = Array.isArray(datasetKeys) ? datasetKeys : [];
  return {
    id: createLocalId("semantic-relationship"),
    name: firstKey && secondKey ? `${firstKey}_to_${secondKey}` : "",
    sourceDataset: firstKey,
    sourceField: "",
    targetDataset: secondKey,
    targetField: "",
    type: "many_to_one",
  };
}

export function buildSemanticDatasetFromRuntimeDataset(datasetDetail, existingKeys = []) {
  const datasetName = String(datasetDetail?.name || "").trim();
  const label = String(datasetDetail?.label || datasetName).trim() || datasetName;
  const relationName =
    String(datasetDetail?.table_name || datasetDetail?.sql_alias || datasetName).trim() || datasetName;
  const semanticKey = uniqueSemanticKey(datasetName || relationName || label, existingKeys);
  const dimensions = [];
  const measures = [];
  const columns = Array.isArray(datasetDetail?.columns) ? datasetDetail.columns : [];

  columns.forEach((column) => {
    const columnName = String(column?.name || "").trim();
    if (!columnName) {
      return;
    }
    const primaryKey = inferPrimaryKey(columnName, datasetName);
    const idLike = columnName === "id" || columnName.endsWith("_id");
    const normalizedType = normalizeSemanticFieldType(column?.data_type, { preferMeasure: true });
    const numericField = normalizedType === "integer" || normalizedType === "number";

    if (numericField && !primaryKey && !idLike) {
      measures.push({
        id: createLocalId("semantic-measure"),
        name: columnName,
        expression: columnName,
        type: "number",
        aggregation: "sum",
      });
      return;
    }

    dimensions.push({
      id: createLocalId("semantic-dimension"),
      name: columnName,
      expression: columnName,
      type: normalizeSemanticFieldType(column?.data_type),
      primaryKey,
    });
  });

  return {
    id: createLocalId("semantic-dataset"),
    sourceDatasetName: datasetName,
    sourceDatasetLabel: label,
    semanticKey,
    relationName,
    description: "",
    dimensions,
    measures,
  };
}

export function buildSemanticModelBuilderState(detail, datasetOptions = []) {
  if (!detail) {
    return {
      name: "",
      description: "",
      semanticDatasets: [],
      relationships: [],
    };
  }

  const model = detail?.content_json && typeof detail.content_json === "object" ? detail.content_json : {};
  const remainingDatasetNames = Array.isArray(detail?.dataset_names)
    ? [...detail.dataset_names]
    : [];
  const datasets = Object.entries(readDatasetMap(model)).map(([semanticKey, value]) => {
    const datasetValue = value && typeof value === "object" ? value : {};
    const relationName = String(
      datasetValue.relation_name || datasetValue.relationName || "",
    ).trim();
    let matchedDataset = findDatasetOption(datasetOptions, semanticKey, relationName);
    if (!matchedDataset && remainingDatasetNames.includes(semanticKey)) {
      matchedDataset =
        (Array.isArray(datasetOptions) ? datasetOptions : []).find(
          (item) => String(item?.name || "").trim() === semanticKey,
        ) || null;
    }
    if (!matchedDataset && remainingDatasetNames.length === 1) {
      matchedDataset =
        (Array.isArray(datasetOptions) ? datasetOptions : []).find(
          (item) => String(item?.name || "").trim() === String(remainingDatasetNames[0] || "").trim(),
        ) || null;
    }
    const matchedDatasetName = String(matchedDataset?.name || "").trim();
    if (matchedDatasetName) {
      const matchedIndex = remainingDatasetNames.findIndex(
        (item) => String(item || "").trim() === matchedDatasetName,
      );
      if (matchedIndex >= 0) {
        remainingDatasetNames.splice(matchedIndex, 1);
      }
    }

    return {
      id: createLocalId("semantic-dataset"),
      sourceDatasetName: String(matchedDataset?.name || semanticKey).trim(),
      sourceDatasetLabel: String(matchedDataset?.label || matchedDataset?.name || semanticKey).trim(),
      semanticKey,
      relationName:
        relationName ||
        String(matchedDataset?.sql_alias || matchedDataset?.name || semanticKey).trim(),
      description: String(datasetValue.description || "").trim(),
      dimensions: Array.isArray(datasetValue.dimensions)
        ? datasetValue.dimensions.map((item) => buildDimensionField(item))
        : [],
      measures: Array.isArray(datasetValue.measures)
        ? datasetValue.measures.map((item) => buildMeasureField(item))
        : [],
    };
  });

  const relationships = Array.isArray(model.relationships)
    ? model.relationships.map((item) => buildRelationship(item))
    : [];

  return {
    name: String(detail?.name || model?.name || "").trim(),
    description: String(detail?.description || model?.description || "").trim(),
    semanticDatasets: datasets,
    relationships,
  };
}

export function cloneSemanticModelBuilderState(state) {
  return {
    name: String(state?.name || ""),
    description: String(state?.description || ""),
    semanticDatasets: (Array.isArray(state?.semanticDatasets) ? state.semanticDatasets : []).map(
      (dataset) => ({
        ...dataset,
        dimensions: (Array.isArray(dataset?.dimensions) ? dataset.dimensions : []).map((field) => ({
          ...field,
        })),
        measures: (Array.isArray(dataset?.measures) ? dataset.measures : []).map((field) => ({
          ...field,
        })),
      }),
    ),
    relationships: (Array.isArray(state?.relationships) ? state.relationships : []).map(
      (relationship) => ({
        ...relationship,
      }),
    ),
  };
}

export function buildSemanticModelDefinition(builderState) {
  const semanticDatasets = Array.isArray(builderState?.semanticDatasets)
    ? builderState.semanticDatasets
    : [];
  const relationships = Array.isArray(builderState?.relationships) ? builderState.relationships : [];

  return {
    version: "1",
    name: String(builderState?.name || "").trim() || undefined,
    description: String(builderState?.description || "").trim() || undefined,
    datasets: Object.fromEntries(
      semanticDatasets.map((dataset) => [
        String(dataset.semanticKey).trim(),
        {
          relation_name:
            String(dataset.relationName || dataset.sourceDatasetName || dataset.semanticKey).trim() ||
            undefined,
          description: String(dataset.description || "").trim() || undefined,
          dimensions: (Array.isArray(dataset.dimensions) ? dataset.dimensions : [])
            .filter((field) => String(field?.name || "").trim())
            .map((field) => ({
              name: String(field.name).trim(),
              expression: String(field.expression || field.name).trim(),
              type: String(field.type || "string").trim() || "string",
              primary_key: Boolean(field.primaryKey),
            })),
          measures: (Array.isArray(dataset.measures) ? dataset.measures : [])
            .filter((field) => String(field?.name || "").trim())
            .map((field) => ({
              name: String(field.name).trim(),
              expression: String(field.expression || field.name).trim(),
              type: String(field.type || "number").trim() || "number",
              aggregation: String(field.aggregation || "sum").trim() || "sum",
            })),
        },
      ]),
    ),
    relationships: relationships
      .filter(
        (relationship) =>
          String(relationship?.name || "").trim() &&
          String(relationship?.sourceDataset || "").trim() &&
          String(relationship?.sourceField || "").trim() &&
          String(relationship?.targetDataset || "").trim() &&
          String(relationship?.targetField || "").trim(),
      )
      .map((relationship) => ({
        name: String(relationship.name).trim(),
        source_dataset: String(relationship.sourceDataset).trim(),
        source_field: String(relationship.sourceField).trim(),
        target_dataset: String(relationship.targetDataset).trim(),
        target_field: String(relationship.targetField).trim(),
        type: String(relationship.type || "many_to_one").trim() || "many_to_one",
      })),
  };
}

export function buildSemanticModelRequest(builderState) {
  const semanticDatasets = Array.isArray(builderState?.semanticDatasets)
    ? builderState.semanticDatasets
    : [];
  const normalizedName = String(builderState?.name || "").trim();
  if (!normalizedName) {
    throw new Error("Semantic model name is required.");
  }
  if (semanticDatasets.length === 0) {
    throw new Error("Select at least one dataset for the semantic model.");
  }

  const datasetNames = semanticDatasets
    .map((dataset) => String(dataset?.sourceDatasetName || "").trim())
    .filter(Boolean);
  if (datasetNames.length === 0) {
    throw new Error("Selected semantic datasets must be bound to runtime datasets.");
  }

  const semanticKeys = semanticDatasets.map((dataset) => String(dataset?.semanticKey || "").trim());
  if (semanticKeys.some((key) => !key)) {
    throw new Error("Each semantic dataset requires a semantic key.");
  }
  if (new Set(semanticKeys).size !== semanticKeys.length) {
    throw new Error("Semantic dataset keys must be unique.");
  }

  const incompleteRelationships = (Array.isArray(builderState?.relationships)
    ? builderState.relationships
    : []
  ).some((relationship) => {
    const values = [
      relationship?.name,
      relationship?.sourceDataset,
      relationship?.sourceField,
      relationship?.targetDataset,
      relationship?.targetField,
    ].map((value) => String(value || "").trim());
    const filled = values.filter(Boolean).length;
    return filled > 0 && filled < values.length;
  });
  if (incompleteRelationships) {
    throw new Error("Complete or remove unfinished relationships before saving.");
  }

  return {
    name: normalizedName,
    description: String(builderState?.description || "").trim(),
    datasets: Array.from(new Set(datasetNames)),
    model: buildSemanticModelDefinition(builderState),
  };
}
