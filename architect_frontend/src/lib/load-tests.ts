import fs from 'fs/promises';
import path from 'path';
import { TestDefinition } from '@/types/test-runner';

// Define where the JSON files live relative to the project root
// process.cwd() in Next.js points to the root of the project (architect_frontend)
const REQUESTS_DIR = path.join(process.cwd(), 'src', 'data', 'requests');

export async function loadTestRequests(): Promise<TestDefinition[]> {
  try {
    // 1. Ensure directory exists to prevent ENOENT errors on fresh clones
    await fs.access(REQUESTS_DIR).catch(() => 
      fs.mkdir(REQUESTS_DIR, { recursive: true })
    );

    // 2. Read all files in the directory
    const files = await fs.readdir(REQUESTS_DIR);
    
    // 3. Filter for JSON files only
    const jsonFiles = files.filter(f => f.endsWith('.json'));

    const tests: TestDefinition[] = [];

    // 4. Parse JSON content
    for (const file of jsonFiles) {
      const filePath = path.join(REQUESTS_DIR, file);
      try {
        const content = await fs.readFile(filePath, 'utf-8');
        const data = JSON.parse(content);
        
        // Basic validation: ensure required fields exist (optional but good practice)
        if (!data.label || !data.endpoint) {
            console.warn(`[LoadTests] Skipping invalid file: ${file}`);
            continue;
        }

        tests.push({
          ...data,
          // If ID is missing in the JSON, use the filename without extension as a fallback
          id: data.id || file.replace(/\.json$/, ''), 
        });
      } catch (e) {
        console.error(`[LoadTests] Failed to parse file: ${file}`, e);
      }
    }

    // 5. Sort alphabetically by label for the UI dropdown
    return tests.sort((a, b) => a.label.localeCompare(b.label));
  } catch (error) {
    console.error("[LoadTests] Critical error loading tests:", error);
    // Return empty array so the page renders (with empty state) instead of crashing
    return [];
  }
}