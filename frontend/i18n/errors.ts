import { messages } from "./messages";
import { translate, localizeKnownMessage } from "./format";
export type Violation = {
  field: string;
  original_value?: string;
  type: string;
  context?: Record<string, string | number>;
};
export function validationMessage(v: Violation) {
  const field = v.field.split(".").at(-1)!;
  const label = Object.hasOwn(messages.en.fields, field)
    ? translate("fields." + field)
    : Object.hasOwn(messages.en.auction, field)
      ? translate("auction." + field)
      : v.field;
  const key = Object.hasOwn(messages.en.validation, v.type)
    ? v.type
    : "unknown";
  return label + ": " + translate("validation." + key, v.context);
}
export class ApiError extends Error {
  constructor(
    public code: string,
    public violations: Violation[] = [],
  ) {
    super(code);
  }
}
export function errorMessage(error: unknown): string {
  if (error instanceof ApiError)
    return error.violations.length
      ? error.violations.map(validationMessage).join("؛ ")
      : translate(
          "errors." +
            (Object.hasOwn(messages.en.errors, error.code)
              ? error.code
              : "UNKNOWN"),
        );
  if (error instanceof Error && !(error instanceof TypeError))
    return localizeKnownMessage(error.message) === error.message
      ? translate("errors.UNKNOWN")
      : localizeKnownMessage(error.message);
  return translate("errors.UNKNOWN");
}
