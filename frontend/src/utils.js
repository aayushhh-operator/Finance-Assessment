export function currency(value) {
  const amount = Number(value ?? 0);
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 2,
  }).format(amount);
}

export function shortDate(value) {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("en-IN", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  }).format(date);
}

export function dateInputValue(value) {
  if (!value) return "";
  return String(value).slice(0, 10);
}

export function titleCase(value) {
  return String(value ?? "")
    .split("_")
    .join(" ")
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

export function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

export function fieldErrorMap(error) {
  if (!error?.validationErrors?.length) return {};
  return error.validationErrors.reduce((acc, item) => {
    const field = item.field?.replace(/^body\./, "") ?? "form";
    acc[field] = item.message;
    return acc;
  }, {});
}
