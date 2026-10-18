"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ImagePlus, Star, Trash2 } from "lucide-react";
import { useRef, useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ConfirmDialog } from "@/components/ui/overlay";
import { EmptyState, ErrorState, Skeleton } from "@/components/ui/states";
import { Alert, Badge, Card } from "@/components/ui/surface";
import { deletePhoto, fetchOwnerPhotos, mediaUrl, setPhotoCover, updatePhoto, uploadPhoto } from "@/lib/api/libraries";
import { userMessage } from "@/lib/errors";
import { queryKeys } from "@/lib/query-keys";
import type { OwnerPhoto } from "@/lib/types";

const MAX_BYTES = 5 * 1024 * 1024;
const ACCEPT = "image/jpeg,image/png,image/webp";

type UploadState = { name: string; status: "uploading" | "done" | "failed"; message?: string };

function PhotoCard({ photo, index }: { photo: OwnerPhoto; index: number }) {
  const queryClient = useQueryClient();
  const [caption, setCaption] = useState(photo.caption);
  const [confirming, setConfirming] = useState(false);
  const refresh = () => queryClient.invalidateQueries({ queryKey: queryKeys.ownerPhotos });

  const cover = useMutation({
    mutationFn: () => setPhotoCover(photo.id),
    onSuccess: async () => {
      await refresh();
      toast.success("Cover photo changed.");
    },
    onError: (error) => toast.error(userMessage(error)),
  });
  const saveCaption = useMutation({
    mutationFn: () => updatePhoto(photo.id, { caption: caption.trim() }),
    onSuccess: async () => {
      await refresh();
      toast.success("Caption saved.");
    },
    onError: (error) => toast.error(userMessage(error)),
  });
  const remove = useMutation({
    mutationFn: () => deletePhoto(photo.id),
    onSuccess: async () => {
      setConfirming(false);
      await refresh();
      toast.success("Photo deleted.");
    },
    onError: (error) => toast.error(userMessage(error)),
  });

  return (
    <Card className="overflow-hidden">
      {/* eslint-disable-next-line @next/next/no-img-element -- photos come from the object store */}
      <img
        src={mediaUrl(photo.thumb_url)}
        alt={photo.caption || `Library photo ${index + 1}`}
        width={photo.width}
        height={photo.height}
        loading="lazy"
        className="aspect-[4/3] w-full object-cover"
      />
      <div className="flex flex-col gap-2 p-3">
        {photo.is_cover && (
          <Badge tone="brand" className="self-start">
            Cover photo
          </Badge>
        )}
        <Input
          aria-label={`Caption for photo ${index + 1}`}
          placeholder="Add a caption"
          maxLength={150}
          value={caption}
          onChange={(event) => setCaption(event.target.value)}
        />
        <div className="flex flex-wrap gap-2">
          <Button
            size="sm"
            variant="secondary"
            disabled={caption.trim() === photo.caption}
            loading={saveCaption.isPending}
            onClick={() => saveCaption.mutate()}
          >
            Save caption
          </Button>
          {!photo.is_cover && (
            <Button size="sm" variant="secondary" loading={cover.isPending} onClick={() => cover.mutate()}>
              <Star aria-hidden="true" className="size-4" /> Make cover
            </Button>
          )}
          <Button size="sm" variant="danger" aria-label={`Delete photo ${index + 1}`} onClick={() => setConfirming(true)}>
            <Trash2 aria-hidden="true" className="size-4" /> Delete
          </Button>
        </div>
      </div>
      <ConfirmDialog
        open={confirming}
        onOpenChange={setConfirming}
        title="Delete this photo?"
        description={
          photo.is_cover
            ? "This is your cover photo. The next photo in order becomes the cover. This can't be undone."
            : "This can't be undone."
        }
        confirmLabel="Delete photo"
        destructive
        loading={remove.isPending}
        onConfirm={() => remove.mutate()}
      />
    </Card>
  );
}

/** Photo gallery management (#25-#29): multi-file upload, cover, captions, delete. */
export function PhotosPanel() {
  const queryClient = useQueryClient();
  const input = useRef<HTMLInputElement>(null);
  const [uploads, setUploads] = useState<UploadState[]>([]);
  const [busy, setBusy] = useState(false);
  const photos = useQuery({ queryKey: queryKeys.ownerPhotos, queryFn: fetchOwnerPhotos });

  const uploadAll = async (files: File[]) => {
    setBusy(true);
    setUploads(files.map((file) => ({ name: file.name, status: "uploading" })));
    for (const [position, file] of files.entries()) {
      const update = (state: Partial<UploadState>) =>
        setUploads((current) => current.map((item, i) => (i === position ? { ...item, ...state } : item)));
      if (file.size > MAX_BYTES) {
        update({ status: "failed", message: "This file is over 5 MB." });
        continue;
      }
      try {
        await uploadPhoto(file);
        update({ status: "done" });
      } catch (error) {
        update({ status: "failed", message: userMessage(error) });
      }
    }
    await queryClient.invalidateQueries({ queryKey: queryKeys.ownerPhotos });
    setBusy(false);
  };

  return (
    <section aria-labelledby="photos-heading" className="flex flex-col gap-4">
      <div className="flex items-center justify-between gap-3">
        <h2 id="photos-heading" className="text-lg font-semibold text-slate-900">
          Photos
        </h2>
        <Button size="sm" loading={busy} onClick={() => input.current?.click()}>
          <ImagePlus aria-hidden="true" className="size-4" /> Upload photos
        </Button>
        <input
          ref={input}
          type="file"
          accept={ACCEPT}
          multiple
          className="sr-only"
          aria-label="Choose photos to upload"
          tabIndex={-1}
          onChange={(event) => {
            const files = Array.from(event.target.files ?? []);
            event.target.value = "";
            if (files.length > 0) void uploadAll(files);
          }}
        />
      </div>
      <p className="text-sm text-slate-600">JPG, PNG or WEBP, up to 5 MB each. The first photo becomes your cover.</p>

      {uploads.length > 0 && (
        <ul aria-live="polite" className="flex flex-col gap-1 text-sm">
          {uploads.map((upload, i) => (
            <li key={`${upload.name}-${i}`} className={upload.status === "failed" ? "text-red-700" : "text-slate-700"}>
              {upload.name}:{" "}
              {upload.status === "uploading" ? "uploading…" : upload.status === "done" ? "uploaded" : upload.message}
            </li>
          ))}
        </ul>
      )}

      {photos.isPending ? (
        <div aria-busy="true" className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          <span className="sr-only" role="status">
            Loading photos
          </span>
          {Array.from({ length: 3 }, (_, i) => (
            <Skeleton key={i} className="h-56 w-full" />
          ))}
        </div>
      ) : photos.isError ? (
        <ErrorState error={photos.error} onRetry={() => void photos.refetch()} title="We couldn't load your photos." />
      ) : photos.data.length === 0 ? (
        <EmptyState
          title="No photos yet"
          description="Libraries with photos get noticed. Add a few pictures of your reading hall."
        />
      ) : (
        <>
          {photos.data.length >= 15 && <Alert tone="info">You&apos;ve reached the limit of 15 photos.</Alert>}
          <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {photos.data.map((photo, index) => (
              <li key={photo.id}>
                <PhotoCard photo={photo} index={index} />
              </li>
            ))}
          </ul>
        </>
      )}
    </section>
  );
}
