"use client";

import { useState, type InputHTMLAttributes } from "react";
import { useTranslations } from "next-intl";
export default function FileInput(
  props: InputHTMLAttributes<HTMLInputElement>,
) {
  const tr = useTranslations("common");
  const [name, setName] = useState("");
  return (
    <span className="file-control">
      <input
        {...props}
        type="file"
        onChange={(e) => {
          setName(
            Array.from(e.target.files || [])
              .map((f) => f.name)
              .join(", "),
          );
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
