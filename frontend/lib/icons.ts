import {
  Activity,
  BarChart3,
  Database,
  HelpCircle,
  MessageSquare,
  Network,
  Settings,
  ShieldCheck,
  Zap,
} from "lucide-react";
import type { ComponentType } from "react";
import type { IconKey } from "./types";

export const iconMap = {
  activity: Activity,
  barChart: BarChart3,
  database: Database,
  help: HelpCircle,
  message: MessageSquare,
  network: Network,
  settings: Settings,
  shield: ShieldCheck,
  zap: Zap,
} satisfies Record<IconKey, ComponentType<{ className?: string }>>;
