"use client";

import { X } from "lucide-react";
import { Dialog as DialogPrimitive, DropdownMenu as Menu, Tooltip as TooltipPrimitive } from "radix-ui";
import { useRef } from "react";

import { cn } from "@/lib/cn";

import { Button } from "./button";

/**
 * Return focus to whatever opened the dialog, even when it was opened
 * programmatically (e.g. from a menu item) rather than by Dialog.Trigger
 * (UI_ARCHITECTURE.md 11).
 */
function useFocusReturn() {
  const opener = useRef<HTMLElement | null>(null);
  return {
    onOpenAutoFocus: () => {
      opener.current = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    },
    onCloseAutoFocus: (event: Event) => {
      if (opener.current?.isConnected) {
        event.preventDefault();
        opener.current.focus();
      }
    },
  };
}

export const Dialog = DialogPrimitive.Root;
export const DialogTrigger = DialogPrimitive.Trigger;
export const DialogClose = DialogPrimitive.Close;

interface DialogContentProps {
  title: string;
  description?: string;
  children?: React.ReactNode;
  footer?: React.ReactNode;
  className?: string;
}

/** Centred dialog: focus is trapped, Esc closes, focus returns to the trigger (Radix). */
export function DialogContent({ title, description, children, footer, className }: DialogContentProps) {
  const focusReturn = useFocusReturn();
  return (
    <DialogPrimitive.Portal>
      <DialogPrimitive.Overlay className="fixed inset-0 z-40 bg-slate-900/50" />
      <DialogPrimitive.Content
        {...focusReturn}
        className={cn(
          "fixed left-1/2 top-1/2 z-50 flex max-h-[90vh] w-[calc(100%-2rem)] max-w-lg -translate-x-1/2 -translate-y-1/2 flex-col",
          "rounded-xl bg-white shadow-lg focus:outline-none",
          className,
        )}
      >
        <DialogHeader title={title} description={description} />
        <div className="overflow-y-auto px-5 pb-5">{children}</div>
        {footer && <div className="flex flex-wrap justify-end gap-2 border-t border-slate-200 px-5 py-4">{footer}</div>}
      </DialogPrimitive.Content>
    </DialogPrimitive.Portal>
  );
}

function DialogHeader({ title, description }: { title: string; description?: string }) {
  return (
    <div className="flex items-start justify-between gap-4 p-5">
      <div className="flex flex-col gap-1">
        <DialogPrimitive.Title className="text-lg font-semibold text-slate-900">{title}</DialogPrimitive.Title>
        {description ? (
          <DialogPrimitive.Description className="text-sm text-slate-600">{description}</DialogPrimitive.Description>
        ) : (
          <DialogPrimitive.Description className="sr-only">{title}</DialogPrimitive.Description>
        )}
      </div>
      <DialogPrimitive.Close
        aria-label="Close"
        className="rounded-md p-1 text-slate-500 hover:bg-slate-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-600"
      >
        <X aria-hidden="true" className="size-5" />
      </DialogPrimitive.Close>
    </div>
  );
}

/** Bottom sheet on phones, side panel on desktop (UI_ARCHITECTURE.md 5.8). */
export function SheetContent({ title, description, children, footer, className }: DialogContentProps) {
  const focusReturn = useFocusReturn();
  return (
    <DialogPrimitive.Portal>
      <DialogPrimitive.Overlay className="fixed inset-0 z-40 bg-slate-900/50" />
      <DialogPrimitive.Content
        {...focusReturn}
        className={cn(
          "fixed inset-x-0 bottom-0 z-50 flex max-h-[85vh] flex-col rounded-t-2xl bg-white shadow-lg focus:outline-none",
          "lg:inset-y-0 lg:left-auto lg:right-0 lg:max-h-none lg:w-[420px] lg:rounded-none lg:rounded-l-2xl",
          className,
        )}
      >
        <DialogHeader title={title} description={description} />
        <div className="flex-1 overflow-y-auto px-5 pb-5">{children}</div>
        {footer && <div className="flex flex-wrap justify-end gap-2 border-t border-slate-200 px-5 py-4">{footer}</div>}
      </DialogPrimitive.Content>
    </DialogPrimitive.Portal>
  );
}

export interface ConfirmDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  /** The consequence, in plain words. */
  description: string;
  confirmLabel: string;
  onConfirm: () => void;
  destructive?: boolean;
  loading?: boolean;
  children?: React.ReactNode;
}

/** Confirmation for destructive actions; the confirm button is on the right (UI_ARCHITECTURE.md 10.4). */
export function ConfirmDialog({
  open,
  onOpenChange,
  title,
  description,
  confirmLabel,
  onConfirm,
  destructive = false,
  loading = false,
  children,
}: ConfirmDialogProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        title={title}
        description={description}
        footer={
          <>
            <DialogClose asChild>
              <Button variant="secondary" disabled={loading}>
                Cancel
              </Button>
            </DialogClose>
            <Button variant={destructive ? "danger" : "primary"} loading={loading} onClick={onConfirm}>
              {confirmLabel}
            </Button>
          </>
        }
      >
        {children}
      </DialogContent>
    </Dialog>
  );
}

export const DropdownMenu = Menu.Root;
export const DropdownMenuTrigger = Menu.Trigger;

export function DropdownMenuContent({ children, align = "end" }: { children: React.ReactNode; align?: "start" | "end" }) {
  return (
    <Menu.Portal>
      <Menu.Content
        align={align}
        sideOffset={6}
        className="z-50 min-w-48 rounded-lg border border-slate-200 bg-white p-1 shadow-lg"
      >
        {children}
      </Menu.Content>
    </Menu.Portal>
  );
}

export function DropdownMenuItem({
  children,
  onSelect,
  destructive,
  asChild,
}: {
  children: React.ReactNode;
  onSelect?: () => void;
  destructive?: boolean;
  /** Render the child (e.g. a Link) as the menu item, so keyboard selection follows the link. */
  asChild?: boolean;
}) {
  return (
    <Menu.Item
      asChild={asChild}
      onSelect={onSelect}
      className={cn(
        "flex h-10 cursor-pointer select-none items-center gap-2 rounded-md px-3 text-sm outline-none data-[highlighted]:bg-slate-100",
        destructive ? "text-red-700" : "text-slate-900",
      )}
    >
      {children}
    </Menu.Item>
  );
}

export const DropdownMenuSeparator = () => <Menu.Separator className="my-1 h-px bg-slate-200" />;

export function Tooltip({ content, children }: { content: string; children: React.ReactNode }) {
  return (
    <TooltipPrimitive.Provider delayDuration={300}>
      <TooltipPrimitive.Root>
        <TooltipPrimitive.Trigger asChild>{children}</TooltipPrimitive.Trigger>
        <TooltipPrimitive.Portal>
          <TooltipPrimitive.Content sideOffset={6} className="z-50 rounded-md bg-slate-900 px-2.5 py-1.5 text-xs text-white shadow">
            {content}
          </TooltipPrimitive.Content>
        </TooltipPrimitive.Portal>
      </TooltipPrimitive.Root>
    </TooltipPrimitive.Provider>
  );
}
