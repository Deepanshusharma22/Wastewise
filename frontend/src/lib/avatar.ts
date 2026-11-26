"use client";

/**
 * Avatar upload with a **server-generated** object path.
 *
 * Bug fixed here: the old Settings page uploaded to `<uid>/avatar.jpg`, while the API
 * only accepts `<uid>/avatar-<8 hex>.<ext>`, so account deletion never removed avatars.
 * In local mode the API generates the path and stores the file; with Supabase the
 * browser uploads to a path that follows the same documented rules.
 */
import { getSupabase } from "@/lib/supabase/client";

const ALLOWED = ["image/jpeg", "image/png", "image/webp"];
/** iPhone HEIC/HEIF: not uploadable as-is, but the browser can decode + re-encode them. */
export const HEIF_TYPES = ["image/heic", "image/heif", "image/heic-sequence", "image/heif-sequence"];
export const MAX_AVATAR_BYTES = 2 * 1024 * 1024;

export function avatarPath(userId: string, type: string): string {
  const ext = type === "image/png" ? "png" : type === "image/webp" ? "webp" : "jpg";
  const suffix = Math.random().toString(16).slice(2, 10).padEnd(8, "0");
  return `${userId}/avatar-${suffix}.${ext}`;
}

/** Can this file be turned into a JPEG in the browser? */
export function uploadable(type: string, name: string): boolean {
  return ALLOWED.includes(type) || HEIF_TYPES.includes(type) || /\.hei[cf]$/i.test(name);
}

export async function normalizeImageToJpeg(file: File, maxSide = 1024): Promise<File> {
  // HEIC/HEIF or anything the browser can decode is normalised to JPEG before upload.
  try {
    const bmp = await createImageBitmap(file, { imageOrientation: "from-image" });
    const scale = Math.min(1, maxSide / Math.max(bmp.width, bmp.height));
    const canvas = document.createElement("canvas");
    canvas.width = Math.round(bmp.width * scale);
    canvas.height = Math.round(bmp.height * scale);
    const ctx = canvas.getContext("2d");
    if (!ctx) return file;
    ctx.fillStyle = "#fff";
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.drawImage(bmp, 0, 0, canvas.width, canvas.height);
    bmp.close();
    const blob = await new Promise<Blob | null>((r) => canvas.toBlob(r, "image/jpeg", 0.9));
    if (!blob) return file;
    return new File([blob], file.name.replace(/\.\w+$/, "") + ".jpg", { type: "image/jpeg" });
  } catch {
    return file;
  }
}

export async function uploadAvatar(
  file: File,
  opts: { mode: "supabase"; userId: string },
): Promise<{ avatarUrl: string | null; error: { name: string; message: string } | null }> {
  if (!ALLOWED.includes(file.type) && !/hei[cf]/i.test(file.type)) {
    return { avatarUrl: null, error: { name: "type", message: "Only JPG, PNG or WEBP images are supported." } };
  }
  const jpeg = await normalizeImageToJpeg(file);
  if (jpeg.size > MAX_AVATAR_BYTES) {
    return { avatarUrl: null, error: { name: "size", message: "Max 2 MB" } };
  }
  const sb = getSupabase();
  const path = avatarPath(opts.userId, jpeg.type);
  const { error } = await sb.storage.from("avatars").upload(path, jpeg, { upsert: true, contentType: jpeg.type, cacheControl: "3600" });
  if (error) return { avatarUrl: null, error: { name: "upload", message: error.message } };
  const { error: dbError } = await sb.from("profiles").update({ avatar_url: path }).eq("id", opts.userId);
  if (dbError) return { avatarUrl: null, error: { name: "profile", message: dbError.message } };
  const { data } = await sb.storage.from("avatars").createSignedUrl(path, 3600);
  return { avatarUrl: data?.signedUrl ? `${data.signedUrl}&v=${Date.now()}` : null, error: null };
}
