/**
 * Generates every raster brand asset for both domains from one source, so
 * illinoisjobtracker.com and illinoisjobtracker.app can never drift apart on
 * their icons or link previews.
 *
 * Emits into BOTH repos:
 *   icons/logo-mark.svg    (copied, not generated - hand-authored here)
 *   favicon.ico            16 / 32 / 48
 *   icons/apple-touch-icon.png   180
 *   icons/icon-192.png     PWA
 *   icons/icon-512.png     PWA, maskable-safe
 *   og-image.png           1200x630 link preview
 *
 * Run:
 *   npm i sharp satori          # deliberately not a dependency of either site
 *   node generate-assets.mjs [appStaticDir] [marketingPublicDir]
 *
 * Fonts are read from the app @fontsource packages - the same faces both sites
 * render - so the wordmark on the OG card is real Chivo Black.
 */
import { readFile, writeFile, mkdir, copyFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import path from "node:path";
import sharp from "sharp";
import satori from "satori";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const APP_OUT = process.argv[2] || path.join(HERE, "../frontend/static");
const MKT_OUT =
  process.argv[3] || path.join(HERE, "../../../ijt-marketing/public");
// Overridable so the script can be run from a throwaway dir that has sharp and
// satori installed, while still reading the real fonts out of the app repo.
const FONT_DIR =
  process.env.IJT_FONT_DIR ||
  path.join(HERE, "../frontend/node_modules/@fontsource");

const BLUE = "#0033A0";
const INK = "#09090B";
const MUTED = "#52525B";
const RED = "#DC2626";

const markSvg = await readFile(path.join(HERE, "logo-mark.svg"));

/* ---------------------------------------------------------------- icons -- */

const png = (size) =>
  sharp(markSvg, { density: 384 })
    .resize(size, size)
    .png({ compressionLevel: 9 })
    .toBuffer();

/** Minimal ICO container wrapping PNG payloads (the modern, widely-supported form). */
function buildIco(images) {
  const header = Buffer.alloc(6);
  header.writeUInt16LE(0, 0); // reserved
  header.writeUInt16LE(1, 2); // type: icon
  header.writeUInt16LE(images.length, 4);

  let offset = 6 + images.length * 16;
  const entries = images.map(({ size, data }) => {
    const e = Buffer.alloc(16);
    e.writeUInt8(size >= 256 ? 0 : size, 0); // width
    e.writeUInt8(size >= 256 ? 0 : size, 1); // height
    e.writeUInt8(0, 2); // palette
    e.writeUInt8(0, 3); // reserved
    e.writeUInt16LE(1, 4); // color planes
    e.writeUInt16LE(32, 6); // bits per pixel
    e.writeUInt32LE(data.length, 8);
    e.writeUInt32LE(offset, 12);
    offset += data.length;
    return e;
  });

  return Buffer.concat([header, ...entries, ...images.map((i) => i.data)]);
}

/* ------------------------------------------------------------- og image -- */

// The mark, rebuilt out of boxes. Same geometry as logo-mark.svg (64-unit grid
// scaled by s), so the OG card and the favicon show an identical mark.
function mark(s) {
  const u = s / 64;
  const box = (x, y, w, h) => ({
    type: "div",
    props: {
      style: {
        position: "absolute",
        left: x * u,
        top: y * u,
        width: w * u,
        height: h * u,
        background: "#fff",
      },
    },
  });
  return {
    type: "div",
    props: {
      style: {
        position: "relative",
        display: "flex",
        width: s,
        height: s,
        background: BLUE,
      },
      children: [
        box(15, 17, 9, 30), // I
        box(28, 17, 9, 30), // L stem
        box(28, 38, 21, 9), // L foot
      ],
    },
  };
}

const ogTree = {
  type: "div",
  props: {
    style: {
      display: "flex",
      flexDirection: "column",
      width: 1200,
      height: 630,
      background: "#FFFFFF",
      fontFamily: "IBM Plex Sans",
    },
    children: [
      // The brand bar - the same Illinois stripe that opens every page.
      {
        type: "div",
        props: {
          style: {
            display: "flex",
            width: 1200,
            height: 14,
            backgroundImage: `linear-gradient(90deg, ${BLUE} 0%, ${BLUE} 60%, ${RED} 60%, ${RED} 70%, #FFFFFF 70%, #FFFFFF 100%)`,
          },
        },
      },
      {
        type: "div",
        props: {
          style: {
            display: "flex",
            flexDirection: "column",
            flex: 1,
            padding: "64px 80px",
            justifyContent: "space-between",
          },
          children: [
            {
              type: "div",
              props: {
                style: { display: "flex", alignItems: "center", gap: 24 },
                children: [
                  mark(80),
                  {
                    type: "div",
                    props: {
                      style: {
                        display: "flex",
                        fontFamily: "Chivo",
                        fontWeight: 900,
                        fontSize: 36,
                        letterSpacing: "-0.015em",
                        color: INK,
                      },
                      children: "Illinois Job Tracker",
                    },
                  },
                ],
              },
            },
            {
              type: "div",
              props: {
                style: { display: "flex", flexDirection: "column", gap: 20 },
                children: [
                  {
                    type: "div",
                    props: {
                      style: {
                        display: "flex",
                        fontFamily: "Chivo",
                        fontWeight: 900,
                        fontSize: 66,
                        lineHeight: 1.05,
                        letterSpacing: "-0.03em",
                        color: INK,
                      },
                      children: "Stay compliant. Get paid.",
                    },
                  },
                  {
                    type: "div",
                    props: {
                      style: {
                        display: "flex",
                        fontSize: 27,
                        lineHeight: 1.4,
                        color: MUTED,
                        maxWidth: 900,
                      },
                      children:
                        "Track your weekly work-search contacts and generate your ADJ034F — without the spreadsheet.",
                    },
                  },
                ],
              },
            },
            {
              type: "div",
              props: {
                style: {
                  display: "flex",
                  fontSize: 17,
                  fontWeight: 600,
                  letterSpacing: "0.2em",
                  color: MUTED,
                },
                children: "WORK SEARCH COMPLIANCE · ILLINOIS",
              },
            },
          ],
        },
      },
    ],
  },
};

/* --------------------------------------------------------------- write --- */

const fonts = [
  {
    name: "Chivo",
    data: await readFile(
      path.join(FONT_DIR, "chivo/files/chivo-latin-900-normal.woff"),
    ),
    weight: 900,
    style: "normal",
  },
  {
    name: "IBM Plex Sans",
    data: await readFile(
      path.join(
        FONT_DIR,
        "ibm-plex-sans/files/ibm-plex-sans-latin-400-normal.woff",
      ),
    ),
    weight: 400,
    style: "normal",
  },
  {
    name: "IBM Plex Sans",
    data: await readFile(
      path.join(
        FONT_DIR,
        "ibm-plex-sans/files/ibm-plex-sans-latin-600-normal.woff",
      ),
    ),
    weight: 600,
    style: "normal",
  },
];

const ogSvg = await satori(ogTree, { width: 1200, height: 630, fonts });
const ogPng = await sharp(Buffer.from(ogSvg))
  .png({ compressionLevel: 9 })
  .toBuffer();

const assets = {
  "favicon.ico": buildIco([
    { size: 16, data: await png(16) },
    { size: 32, data: await png(32) },
    { size: 48, data: await png(48) },
  ]),
  "apple-touch-icon.png": await png(180),
  "icon-192.png": await png(192),
  "icon-512.png": await png(512),
  "og-image.png": ogPng,
};

for (const dir of [APP_OUT, MKT_OUT]) {
  await mkdir(path.join(dir, "icons"), { recursive: true });
  for (const [name, data] of Object.entries(assets)) {
    // favicon.ico and og-image.png sit at the root so the default browser and
    // crawler lookups find them; the rest live under /icons/.
    const target =
      name === "favicon.ico" || name === "og-image.png"
        ? path.join(dir, name)
        : path.join(dir, "icons", name);
    await writeFile(target, data);
    console.log(`  ${target}  ${data.length} bytes`);
  }
  await copyFile(
    path.join(HERE, "logo-mark.svg"),
    path.join(dir, "icons", "logo-mark.svg"),
  );
}

console.log("\ndone - identical assets written to both repos");
