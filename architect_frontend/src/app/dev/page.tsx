import fs from "fs/promises";
import path from "path";
import DevDashboard from "./dashboard";
import { INVENTORY } from "../tools/inventory";
import type { TestDefinition } from "@/types/test-runner";

async function getAvailableTests(): Promise<TestDefinition[]> {
  try {
    // Defines the path: src/data/requests
    const dataDir = path.join(process.cwd(), "src/data/requests");
    
    // Check if directory exists
    try {
        await fs.access(dataDir);
    } catch {
        console.warn(`Test directory not found at: ${dataDir}`);
        return [];
    }

    const files = await fs.readdir(dataDir);
    
    // Filter for JSON files and read them
    const tests = await Promise.all(
      files
        .filter((f) => f.endsWith(".json"))
        .map(async (f) => {
          try {
            const content = await fs.readFile(path.join(dataDir, f), "utf-8");
            return JSON.parse(content) as TestDefinition;
          } catch (e) {
            console.error(`Failed to parse test file ${f}`, e);
            return null;
          }
        })
    );

    // Filter out any failed parses (nulls)
    return tests.filter((t): t is TestDefinition => t !== null);
  } catch (error) {
    console.error("Error loading test definitions:", error);
    return [];
  }
}

export default async function DevPage() {
  const tests = await getAvailableTests();

  // We pass the INVENTORY to the dashboard so it can locate the 
  // new "Expert" tools (Profiler, Ambiguity Detector) for the 
  // Advanced Diagnostics tab.
  return (
    <DevDashboard 
      availableTests={tests} 
      inventory={INVENTORY}
    />
  );
}