import { Extractor } from "~/types";

export const currentPostUrl = (location: string): string => {
  const match = location.match(/^\/post\/(.+)$/);
  return match ? decodeURIComponent(match[1]) : "";
};

export const resolveExtractorUrl = (
  ext: Extractor,
  {
    filterValue = "",
    searchValue = "",
    contextUrl = "",
  }: { filterValue?: string; searchValue?: string; contextUrl?: string } = {},
): string => {
  let url = ext.url;
  const urlPathParts = url.split("?")[0].split("/").filter(Boolean);
  const hasQueryGroup = ext.groups.some((g) => g === "QUERY");
  for (const [i, group] of ext.groups.entries()) {
    if (!group) continue;
    const raw = group.split("/").filter(Boolean).pop() ?? group;
    let value: string;
    if (ext.filters && raw === "FILTER") {
      value = filterValue;
    } else if (hasQueryGroup ? raw === "QUERY" : !ext.filters && i === 0) {
      value = encodeURIComponent(searchValue);
    } else {
      const pi = urlPathParts.indexOf(raw);
      const pattern =
        pi > 0 ? new RegExp(`/${urlPathParts[pi - 1]}/([^/?#&]+)/`) : null;
      value = pattern ? (contextUrl.match(pattern)?.[1] ?? "") : "";
    }
    url = url.replace(
      new RegExp(`(^|[^a-zA-Z0-9])${raw}([^a-zA-Z0-9]|$)`, "g"),
      `$1${value}$2`,
    );
  }
  return url;
};

export const hash = (str: string): string => {
  let h = 0x811c9dc5;
  for (let i = 0; i < str.length; i++) {
    h ^= str.charCodeAt(i);
    h = Math.imul(h, 0x01000193) >>> 0;
  }
  return h.toString(16).padStart(8, "0");
};

export const formatNumber = (val: number) =>
  Intl.NumberFormat("en-US", {
    notation: "compact",
    maximumFractionDigits: 1,
  }).format(val);

export const formatTimeAgo = (
  date: Date,
  options: Intl.RelativeTimeFormatOptions = { style: "long" },
) => {
  const elapsed = date.getTime() - Date.now();
  const units = {
    year: 31536000000,
    month: 2628000000,
    day: 86400000,
    hour: 3600000,
    minute: 60000,
    second: 1000,
  };
  const rtf = new Intl.RelativeTimeFormat("en", options);

  for (const [unit, amount] of Object.entries(units)) {
    if (Math.abs(elapsed) > amount || unit === "second") {
      return rtf.format(
        Math.round(elapsed / amount),
        unit as Intl.RelativeTimeFormatUnit,
      );
    }
  }
};
