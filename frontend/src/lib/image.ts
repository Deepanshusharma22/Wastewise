"use client";

/**
 * Phone photos are often > 4 MB. The model only needs 224 px, so large images are re-encoded
 * in the browser (max side 2048 px, JPEG q=0.9, EXIF orientation applied) before upload.
 */
export async function prepareUpload(file: File, maxBytes = 3.5 * 1024 * 1024, maxSide = 2048): Promise<File> {
  if (typeof createImageBitmap !== "function") return file;
  let bmp: ImageBitmap;
  try {
    bmp = await createImageBitmap(file, { imageOrientation: "from-image" });
  } catch {
    return file; // let the server report corrupt/unsupported files
  }
  const longest = Math.max(bmp.width, bmp.height);
  if (file.size <= maxBytes && longest <= 4096) { bmp.close(); return file; }
  const scale = Math.min(1, maxSide / longest);
  const w = Math.round(bmp.width * scale);
  const h = Math.round(bmp.height * scale);
  const canvas = document.createElement("canvas");
  canvas.width = w; canvas.height = h;
  const ctx = canvas.getContext("2d");
  if (!ctx) { bmp.close(); return file; }
  ctx.fillStyle = "#fff";
  ctx.fillRect(0, 0, w, h);
  ctx.drawImage(bmp, 0, 0, w, h);
  bmp.close();
  const blob = await new Promise<Blob | null>((res) => canvas.toBlob(res, "image/jpeg", 0.9));
  if (!blob) return file;
  return new File([blob], file.name.replace(/\.\w+$/, "") + ".jpg", { type: "image/jpeg" });
}
