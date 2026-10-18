"use client";

import { Building2, ChevronLeft, ChevronRight } from "lucide-react";
import { useEffect, useState } from "react";

import { Button, IconButton } from "@/components/ui/button";
import { Dialog, DialogContent } from "@/components/ui/overlay";
import { mediaUrl } from "@/lib/api/libraries";
import type { PublicPhoto } from "@/lib/types";

const THUMBNAILS = 4;

/**
 * Cover large plus up to four thumbnails; "View all" opens the lightbox
 * (UI_ARCHITECTURE.md 5.2). With no photos a neutral placeholder is shown.
 */
export function PhotoGallery({ photos, libraryName }: { photos: PublicPhoto[]; libraryName: string }) {
  const [open, setOpen] = useState(false);
  const [index, setIndex] = useState(0);

  const cover = photos.find((photo) => photo.is_cover) ?? photos[0];
  if (!cover) {
    return (
      <div
        role="img"
        aria-label={`No photos of ${libraryName} yet`}
        className="flex aspect-[16/7] items-center justify-center rounded-xl bg-slate-100 text-slate-400"
      >
        <Building2 aria-hidden="true" className="size-12" />
      </div>
    );
  }

  const others = photos.filter((photo) => photo.id !== cover.id).slice(0, THUMBNAILS);
  const show = (photo: PublicPhoto) => {
    setIndex(photos.findIndex((candidate) => candidate.id === photo.id));
    setOpen(true);
  };

  return (
    <>
      <div className="grid gap-2 sm:grid-cols-4 sm:grid-rows-2">
        <button
          type="button"
          onClick={() => show(cover)}
          className="overflow-hidden rounded-xl focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-600 sm:col-span-2 sm:row-span-2"
        >
          {/* eslint-disable-next-line @next/next/no-img-element -- photos come from the object store */}
          <img
            src={mediaUrl(cover.url)}
            alt={cover.caption || `${libraryName}, cover photo`}
            className="aspect-[4/3] size-full object-cover sm:aspect-auto"
          />
        </button>
        {others.map((photo) => (
          <button
            key={photo.id}
            type="button"
            onClick={() => show(photo)}
            className="hidden overflow-hidden rounded-xl focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-600 sm:block"
          >
            {/* eslint-disable-next-line @next/next/no-img-element -- photos come from the object store */}
            <img
              src={mediaUrl(photo.thumb_url)}
              alt={photo.caption || `${libraryName}, photo`}
              loading="lazy"
              className="size-full object-cover"
            />
          </button>
        ))}
      </div>
      {photos.length > 1 && (
        <Button variant="secondary" size="sm" className="mt-2" onClick={() => show(cover)}>
          View all {photos.length} photos
        </Button>
      )}
      <Lightbox photos={photos} index={index} onIndexChange={setIndex} open={open} onOpenChange={setOpen} name={libraryName} />
    </>
  );
}

function Lightbox({
  photos,
  index,
  onIndexChange,
  open,
  onOpenChange,
  name,
}: {
  photos: PublicPhoto[];
  index: number;
  onIndexChange: (index: number) => void;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  name: string;
}) {
  const count = photos.length;
  const go = (step: number) => onIndexChange((index + step + count) % count);

  useEffect(() => {
    if (!open) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "ArrowRight") onIndexChange((index + 1) % count);
      if (event.key === "ArrowLeft") onIndexChange((index - 1 + count) % count);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, index, count, onIndexChange]);

  const photo = photos[index];
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent title={`${name} photos`} description={`Photo ${index + 1} of ${count}`} className="max-w-3xl">
        {photo && (
          <figure className="flex flex-col gap-2">
            {/* eslint-disable-next-line @next/next/no-img-element -- photos come from the object store */}
            <img src={mediaUrl(photo.url)} alt={photo.caption || `${name}, photo ${index + 1}`} className="max-h-[60vh] w-full rounded-lg object-contain" />
            {photo.caption && <figcaption className="text-sm text-slate-700">{photo.caption}</figcaption>}
          </figure>
        )}
        {count > 1 && (
          <div className="mt-3 flex justify-between">
            <IconButton label="Previous photo" variant="secondary" icon={<ChevronLeft className="size-5" />} onClick={() => go(-1)} />
            <IconButton label="Next photo" variant="secondary" icon={<ChevronRight className="size-5" />} onClick={() => go(1)} />
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
