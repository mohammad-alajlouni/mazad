"use client";

import { useEffect, useRef, useState, type InputHTMLAttributes } from "react";
import { useTranslations } from "next-intl";
export default function FileInput(
  props: InputHTMLAttributes<HTMLInputElement>,
) {
  const tr = useTranslations("common");
  const [name, setName] = useState("");
  const input = useRef<HTMLInputElement>(null);
  const names = (element: HTMLInputElement) =>
    Array.from(element.files || [])
      .map((f) => f.name)
      .join(", ");
  // The files may be replaced after picking (an edited photograph, or none
  // when the editor was cancelled): show what the input holds now.
  useEffect(() => {
    const element = input.current;
    if (!element) return;
    const replaced = () => setName(names(element));
    element.addEventListener("files-set", replaced);
    return () => element.removeEventListener("files-set", replaced);
  }, []);
  return (
    <span className="file-control">
      <input
        {...props}
        ref={input}
        type="file"
        onChange={(e) => {
          setName(names(e.target));
          props.onChange?.(e);
        }}
      />
      <span aria-hidden="true" className="file-button">
        {tr("chooseFile")}
      </span>
      <span aria-hidden="true" className="file-name">
        {name ? <bdi dir="ltr">{name}</bdi> : tr("noFile")}
      </span>
    </span>
  );
}
