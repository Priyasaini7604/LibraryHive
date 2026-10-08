import {
  Armchair,
  Bell,
  Building2,
  Calendar,
  ChartColumn,
  Clock,
  CreditCard,
  House,
  IdCard,
  Inbox,
  LayoutDashboard,
  MessageSquare,
  Search,
  TriangleAlert,
  User,
  Users,
  Wallet,
} from "lucide-react";

import type { NavIcon as NavIconName } from "@/lib/navigation";

const ICONS = {
  home: House,
  search: Search,
  "id-card": IdCard,
  clock: Clock,
  wallet: Wallet,
  bell: Bell,
  user: User,
  message: MessageSquare,
  calendar: Calendar,
  layout: LayoutDashboard,
  armchair: Armchair,
  users: Users,
  alert: TriangleAlert,
  "credit-card": CreditCard,
  inbox: Inbox,
  building: Building2,
  chart: ChartColumn,
} as const satisfies Record<NavIconName, unknown>;

export function NavIcon({ name, className }: { name: NavIconName; className?: string }) {
  const Icon = ICONS[name];
  return <Icon aria-hidden="true" className={className ?? "size-5"} />;
}
