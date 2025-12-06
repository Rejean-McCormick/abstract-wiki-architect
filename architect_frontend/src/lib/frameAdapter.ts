// architect_frontend/src/lib/frameAdapter.ts

import type { FrameContextConfig, FrameFieldConfig } from "@/components/FrameForm";
import type { FrameTypeMeta } from "@/lib/api";

/**
 * Adapter to convert Backend Metadata + JSON Schema into Frontend Form Configuration.
 * * This allows the frontend to dynamically build forms for any frame type 
 * registered in the backend without hardcoding fields in the UI.
 */
export function adaptFrameConfig(
  meta: FrameTypeMeta,
  schema: Record<string, any>
): FrameContextConfig {
  // JSON Schema "properties" defines the fields
  const properties = schema.properties || {};
  
  // "required" is an array of field names in JSON Schema
  const requiredFields = new Set(Array.isArray(schema.required) ? schema.required : []);

  // Map each schema property to a FrameFieldConfig
  const fields: FrameFieldConfig[] = Object.entries(properties).map(([key, prop]: [string, any]) => {
    // 1. Infer input type from JSON Schema 'type' and field name heuristics
    let inputType: FrameFieldConfig["inputType"] = "text";
    
    if (prop.type === "integer" || prop.type === "number") {
      inputType = "number";
    } else if (prop.type === "boolean") {
      inputType = "checkbox";
    } else if (prop.type === "array") {
      // Arrays of strings are often comma-separated text in simple forms
      inputType = "text"; 
    } else if (prop.type === "object") {
      // Complex nested objects get a JSON editor
      inputType = "json";
    } else if (key.includes("date")) {
      // Heuristic: fields with 'date' in the name use date widgets
      // (You could also check prop.format === 'date' if the backend provides it)
      inputType = "text"; 
    } else if (key === "description" || key === "text" || key.includes("summary")) {
      inputType = "textarea";
    }

    // 2. Handle Enums -> Select Dropdowns
    let options = undefined;
    if (prop.enum && Array.isArray(prop.enum)) {
      inputType = "select";
      options = prop.enum.map((val: string) => ({ 
        label: val, 
        value: val 
      }));
    }

    // 3. Construct the field config
    return {
      name: key,
      // Use the 'title' from schema if present, else capitalized key
      label: prop.title || key.replace(/_/g, " ").replace(/\b\w/g, l => l.toUpperCase()),
      inputType,
      required: requiredFields.has(key),
      placeholder: prop.examples ? String(prop.examples[0]) : undefined,
      helpText: prop.description,
      defaultValue: prop.default,
      options,
    };
  });

  // 4. Return the full context config
  return {
    frameType: meta.frame_type,
    label: meta.title || meta.frame_type,
    description: meta.description,
    defaultLang: "en",
    // These could be fetched dynamically, but hardcoded list is safe for now
    languages: ["en", "fr", "tr", "ja"], 
    fields,
  };
}