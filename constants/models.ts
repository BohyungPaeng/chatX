// constants/models.ts
export interface Model {
  id: string;
  name: string;
}

export const MODEL_PRESETS = {
  "dev": [
    { id: "azure.gpt-4o-2024-11-20", name: "PWCGPT-4o" },
    { id: "gpt-4.1", name: "GPT-4.1" },
    { id: "gpt-4o", name: "GPT-4o" },
    { id: "o4-mini", name: "O4-mini" },
    { id: "o3", name: "O3" },
  ],
  "stage-public": [
    { id: "gpt-4.1", name: "GPT-4.1" },
    { id: "gpt-4o", name: "GPT-4o" },
    { id: "o4-mini", name: "O4-mini" },
    { id: "o3", name: "O3" },
  ],
};

export function getModels(preset: string = "dev"): Model[] {
  return (MODEL_PRESETS as any)[preset] || MODEL_PRESETS["dev"];
}