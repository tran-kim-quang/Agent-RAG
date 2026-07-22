import { DashboardClient } from "@/components/dashboard-client";
import { getDashboardData } from "@/lib/api/dashboard";

export default async function Home() {
  const data = await getDashboardData();

  return <DashboardClient data={data} />;
}
