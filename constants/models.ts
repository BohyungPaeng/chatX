// constants/models.ts
export interface Model {
  id: string;
  name: string;
}

export const MODEL_PRESETS = {
  "internal": [
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
  "dev": [
    { id: "azure.gpt-4o-2024-11-20", name: "PWCGPT-4o" }, //2.75/11$
    { id: "bedrock.anthropic.claude-3-7-sonnet-v1", name: "Anthropic Claude 3.7 Sonnet v1" }, // 3/15$
    { id: "vertex_ai.gemini-2.5-pro-preview-03-25",   name: "Gemini 2.5 Pro Preview" },          // 1.25/10$
    { id: "azure.gpt-4.1-mini-2025-04-14",           name: "PWCGPT-4.1 Mini" },             // 0.4/1.6$
    { id: "bedrock.anthropic.claude-3-5-haiku",      name: "Anthropic Claude 3.5 Haiku" },      // 0.8/4$
    { id: "vertex_ai.gemini-2.5-flash-preview-04-17",name: "Gemini 2.5 Flash Preview" },        // 0.15/0.6$
    { id: "azure.gpt-4.1-2025-04-14",                name: "PWCGPT-4.1" },                  // 2/8$
    { id: "azure.gpt-4.1-nano-2025-04-14",           name: "PWCGPT-4.1 Nano" },             // 0.1/0.4$
    { id: "azure.o3-mini",                           name: "PWCGPT-O3-mini" },                  // 1.21/4.84$
    { id: "azure.o4-mini-2025-04-16",               name: "PWCGPT-O4-mini" },                 // 1.1/4.4$
    { id: "azure.o3-2025-04-16",                    name: "PWCGPT-O3(high cost)" }                       // 10/40$
    // { id: "openai.o4-mini-2025-04-16",               name: "OpenAI O4 Mini" },                 // 1.1/4.4$
    // { id: "openai.o3-2025-04-16",                    name: "OpenAI O3(high cost)" }                       // 10/40$
  ]
};

export function getModels(preset: string = "internal"): Model[] {
  return (MODEL_PRESETS as any)[preset] || MODEL_PRESETS["internal"];
}