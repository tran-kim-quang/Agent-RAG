import {
  chatMessages,
  citations,
  commandCenter,
  corpusSummary,
  documents,
  entityNodes,
  modelConfigs,
  primaryNavigation,
  reasoningSteps,
  systemLogs,
  systemMetrics,
  utilityNavigation,
} from "../mock-data";

export async function getDashboardData() {
  return {
    chatMessages,
    citations,
    commandCenter,
    corpusSummary,
    documents,
    entityNodes,
    modelConfigs,
    primaryNavigation,
    reasoningSteps,
    systemLogs,
    systemMetrics,
    utilityNavigation,
  };
}

export async function getBackendClient() {
  return {
    baseUrl: process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api",
  };
}
