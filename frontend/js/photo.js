// Getting a picture ready to upload, in the browser.
//
// Phone cameras make photos of 10–20 MB (more than the server takes) in formats it may not
// read (HEIC). Every picture is decoded here and sent as a JPEG of at most MAX_SIDE pixels:
// small enough to upload quickly on mobile data, larger than the server keeps (it scales
// down to 1600 px and re-encodes again). Drawing to a canvas also drops the EXIF data, GPS included.

const MAX_SIDE = 2400;
const QUALITY = 0.9;
const SERVER_TYPES = ['image/jpeg', 'image/png', 'image/webp'];
const SERVER_MAX_BYTES = 10 * 1024 * 1024;

/** A JPEG Blob ready for upload. Throws { code } with an error.* code the pages translate. */
export async function preparePhoto(file) {
  let bitmap;
  try {
    // EXIF rotation is applied by default ("from-image").
    bitmap = await createImageBitmap(file);
  } catch {
    // The browser can't read it. The server may still (it reads only what it accepts).
    if (SERVER_TYPES.includes(file.type) && file.size <= SERVER_MAX_BYTES) return file;
    throw Object.assign(new Error('PHOTO_BAD_TYPE'), { code: 'PHOTO_BAD_TYPE' });
  }
  const scale = Math.min(1, MAX_SIDE / Math.max(bitmap.width, bitmap.height));
  const canvas = document.createElement('canvas');
  canvas.width = Math.round(bitmap.width * scale);
  canvas.height = Math.round(bitmap.height * scale);
  const ctx = canvas.getContext('2d');
  ctx.fillStyle = '#fff'; // transparent PNGs: white, as the server does
  ctx.fillRect(0, 0, canvas.width, canvas.height);
  ctx.drawImage(bitmap, 0, 0, canvas.width, canvas.height);
  bitmap.close?.();
  const blob = await new Promise((resolve) => canvas.toBlob(resolve, 'image/jpeg', QUALITY));
  if (!blob) {
    if (SERVER_TYPES.includes(file.type) && file.size <= SERVER_MAX_BYTES) return file;
    throw Object.assign(new Error('PHOTO_BAD_TYPE'), { code: 'PHOTO_BAD_TYPE' });
  }
  return blob;
}
