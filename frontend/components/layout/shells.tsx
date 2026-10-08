"use client";

import { LogOut, Menu as MenuIcon } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogTrigger,
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
  SheetContent,
} from "@/components/ui/overlay";
import { Avatar } from "@/components/ui/surface";
import { useAuth } from "@/lib/auth-context";
import { cn } from "@/lib/cn";
import {
  type NavItem,
  OWNER_MOBILE_INBOX,
  OWNER_NAV,
  STUDENT_MENU,
  STUDENT_NAV,
  activeHref,
} from "@/lib/navigation";

import { NavIcon } from "./nav-icon";

function SkipLink() {
  return (
    <a
      href="#main"
      className="sr-only z-50 rounded-md bg-white px-4 py-2 text-sm font-medium text-blue-700 focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:shadow-lg"
    >
      Skip to content
    </a>
  );
}

function Logo() {
  return (
    <Link href="/" className="flex items-center gap-2 font-semibold text-slate-900">
      <span aria-hidden="true" className="flex size-8 items-center justify-center rounded-lg bg-blue-600 text-sm text-white">
        LH
      </span>
      LibraryHive
    </Link>
  );
}

function NavLink({
  item,
  active,
  compact = false,
  onNavigate,
}: {
  item: NavItem;
  active: boolean;
  compact?: boolean;
  onNavigate?: () => void;
}) {
  return (
    <Link
      href={item.href}
      onClick={onNavigate}
      aria-current={active ? "page" : undefined}
      className={cn(
        "flex items-center gap-2 rounded-lg text-sm font-medium focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-600",
        compact ? "min-h-14 flex-1 flex-col justify-center gap-0.5 text-xs" : "h-10 px-3",
        active ? "bg-blue-50 text-blue-700" : "text-slate-600 hover:bg-slate-100 hover:text-slate-900",
      )}
    >
      <NavIcon name={item.icon} className={compact ? "size-5" : "size-4"} />
      {item.label}
    </Link>
  );
}

function BottomBar({ items, pathname, extra }: { items: NavItem[]; pathname: string; extra?: React.ReactNode }) {
  const active = activeHref(pathname, items);
  return (
    <nav
      aria-label="Primary"
      className="fixed inset-x-0 bottom-0 z-30 flex border-t border-slate-200 bg-white px-1 pb-[env(safe-area-inset-bottom)] lg:hidden"
    >
      {items.map((item) => (
        <NavLink key={item.href} item={item} active={item.href === active} compact />
      ))}
      {extra}
    </nav>
  );
}

function UserMenu({ extraItems = [] }: { extraItems?: NavItem[] }) {
  const { user, logout } = useAuth();
  if (!user) return null;
  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        aria-label="Account menu"
        className="rounded-full focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-600 focus-visible:ring-offset-2"
      >
        <Avatar name={user.name} />
      </DropdownMenuTrigger>
      <DropdownMenuContent>
        <div className="px-3 py-2 text-sm">
          <p className="font-medium text-slate-900">{user.name}</p>
          <p className="text-slate-600">{user.email}</p>
        </div>
        <DropdownMenuSeparator />
        {extraItems.map((item) => (
          <DropdownMenuItem key={item.href} asChild>
            <Link href={item.href}>
              <NavIcon name={item.icon} className="size-4" />
              {item.label}
            </Link>
          </DropdownMenuItem>
        ))}
        <DropdownMenuItem onSelect={() => void logout()}>
          <LogOut aria-hidden="true" className="size-4" /> Log out
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

/** Public pages: discover, library pages, auth (UI_ARCHITECTURE.md 4.1). */
export function PublicShell({ children }: { children: React.ReactNode }) {
  const { status, user } = useAuth();
  return (
    <div className="flex min-h-dvh flex-col">
      <SkipLink />
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex h-16 max-w-7xl items-center justify-between gap-4 px-4 sm:px-6">
          <Logo />
          <nav aria-label="Primary" className="flex items-center gap-2">
            <Link href="/discover" className="hidden h-10 items-center px-3 text-sm font-medium text-slate-700 hover:text-slate-900 sm:flex">
              Discover
            </Link>
            {status === "authenticated" && user ? (
              <Button asChild variant="secondary" size="sm">
                <Link href={user.role === "owner" ? "/owner" : "/student"}>My account</Link>
              </Button>
            ) : (
              <>
                <Button asChild variant="ghost" size="sm">
                  <Link href="/login">Log in</Link>
                </Button>
                <Button asChild size="sm">
                  <Link href="/register">Sign up</Link>
                </Button>
              </>
            )}
          </nav>
        </div>
      </header>
      <main id="main" className="flex-1">
        {children}
      </main>
    </div>
  );
}

/** Student area: top navigation on desktop, bottom tab bar on phones (UI_ARCHITECTURE.md 4.2). */
export function StudentShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const desktopItems = STUDENT_NAV.filter((item) => item.href !== "/student/notifications" && item.href !== "/student/profile");
  const active = activeHref(pathname, STUDENT_NAV);
  return (
    <div className="flex min-h-dvh flex-col bg-slate-50">
      <SkipLink />
      <header className="sticky top-0 z-20 border-b border-slate-200 bg-white">
        <div className="mx-auto flex h-16 max-w-7xl items-center justify-between gap-4 px-4 sm:px-6">
          <Logo />
          <nav aria-label="Student" className="hidden items-center gap-1 lg:flex">
            {desktopItems.map((item) => (
              <NavLink key={item.href} item={item} active={item.href === active} />
            ))}
          </nav>
          <UserMenu extraItems={STUDENT_MENU} />
        </div>
      </header>
      <main id="main" className="mx-auto w-full max-w-7xl flex-1 px-4 pb-24 pt-6 sm:px-6 lg:pb-10">
        {children}
      </main>
      <BottomBar items={STUDENT_NAV.filter((item) => item.mobile)} pathname={pathname} />
    </div>
  );
}

/** Owner area: sidebar on desktop, bottom bar + "More" sheet on phones (UI_ARCHITECTURE.md 4.3). */
export function OwnerShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const [moreOpen, setMoreOpen] = useState(false);
  const active = activeHref(pathname, OWNER_NAV);
  const mobileItems = [...OWNER_NAV.filter((item) => item.mobile), OWNER_MOBILE_INBOX];

  return (
    <div className="flex min-h-dvh bg-slate-50">
      <SkipLink />
      <aside className="sticky top-0 hidden h-dvh w-60 shrink-0 flex-col gap-4 border-r border-slate-200 bg-white p-4 lg:flex">
        <Logo />
        <nav aria-label="Owner" className="flex flex-col gap-1">
          {OWNER_NAV.map((item) => (
            <NavLink key={item.href} item={item} active={item.href === active} />
          ))}
        </nav>
      </aside>
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-20 flex h-16 items-center justify-between gap-4 border-b border-slate-200 bg-white px-4 sm:px-6">
          <div className="lg:hidden">
            <Logo />
          </div>
          <div className="flex-1" />
          <UserMenu />
        </header>
        <main id="main" className="w-full flex-1 px-4 pb-24 pt-6 sm:px-6 lg:pb-10">
          {children}
        </main>
      </div>
      <BottomBar
        items={mobileItems}
        pathname={pathname}
        extra={
          <Dialog open={moreOpen} onOpenChange={setMoreOpen}>
            <DialogTrigger className="flex min-h-14 flex-1 flex-col items-center justify-center gap-0.5 text-xs font-medium text-slate-600">
              <MenuIcon aria-hidden="true" className="size-5" />
              More
            </DialogTrigger>
            <SheetContent title="Menu">
              <nav aria-label="Owner menu" className="flex flex-col gap-1">
                {OWNER_NAV.map((item) => (
                  <NavLink
                    key={item.href}
                    item={item}
                    active={item.href === active}
                    onNavigate={() => setMoreOpen(false)}
                  />
                ))}
              </nav>
            </SheetContent>
          </Dialog>
        }
      />
    </div>
  );
}
