"use client";

import { useParams } from "next/navigation";

import { LibraryPage } from "@/components/library/library-page";

export default function LibraryRoute() {
  const { id } = useParams<{ id: string }>();
  return <LibraryPage id={id} />;
}
