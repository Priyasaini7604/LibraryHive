"use client";

import { useQuery } from "@tanstack/react-query";

import { Button } from "@/components/ui/button";
import { FormField } from "@/components/ui/form-field";
import { Select } from "@/components/ui/choice";
import { Alert } from "@/components/ui/surface";
import { fetchDomains } from "@/lib/api/auth";
import { userMessage } from "@/lib/errors";
import { queryKeys } from "@/lib/query-keys";

const NONE = "none";

/**
 * Optional exam-domain select for students (register and profile). The list comes from the
 * public vocabulary endpoint (#2), never a hardcoded array. The field is optional, so a failed
 * load shows a retry instead of blocking the form.
 */
export function DomainSelect({
  value,
  onChange,
  error,
}: {
  value: string | undefined;
  onChange: (value: string) => void;
  error?: string;
}) {
  const domains = useQuery({ queryKey: queryKeys.domains, queryFn: fetchDomains, staleTime: 60 * 60 * 1000 });

  if (domains.isError) {
    return (
      <Alert
        tone="warning"
        title="We couldn't load the exam list."
        action={
          <Button size="sm" variant="secondary" onClick={() => void domains.refetch()}>
            Try again
          </Button>
        }
      >
        {userMessage(domains.error)} You can choose your exam later in your profile.
      </Alert>
    );
  }

  const options = [
    { value: NONE, label: "Prefer not to say" },
    ...(domains.data ?? []).map((domain) => ({ value: domain.code, label: domain.name })),
  ];

  return (
    <FormField label="Exam you are preparing for" hint="Optional. Helps libraries understand their members." error={error}>
      <Select
        value={value || NONE}
        onValueChange={(next) => onChange(next === NONE ? "" : next)}
        options={options}
        placeholder={domains.isPending ? "Loading…" : "Select an exam"}
        disabled={domains.isPending}
      />
    </FormField>
  );
}
