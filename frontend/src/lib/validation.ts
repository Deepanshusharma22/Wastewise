/** Client-side checks (the server and Supabase enforce their own limits). */
export function passwordStrongEnough(pw: string): boolean {
  return pw.length >= 8 && /[A-Za-z]/.test(pw) && /\d/.test(pw);
}

export const MAX_UPLOAD_BYTES = 4 * 1024 * 1024;
export const ACCEPTED_TYPES = ["image/jpeg", "image/png", "image/webp"] as const;

export type FileProblem = "tooLarge" | "badType" | null;
export function checkFile(file: { size: number; type: string }): FileProblem {
  if (!ACCEPTED_TYPES.includes(file.type as (typeof ACCEPTED_TYPES)[number])) return "badType";
  if (file.size > MAX_UPLOAD_BYTES) return "tooLarge";
  return null;
}
