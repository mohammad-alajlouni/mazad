"use client";

import { createContext, useContext, useEffect, useRef, useState } from "react";
import { useTranslations } from "next-intl";
import { localizeKnownMessage } from "../i18n/format";
const Context = createContext<(message: string) => Promise<boolean>>(
  async () => false,
);
export const useConfirm = () => useContext(Context);
export function ConfirmationProvider({
  children,
}: {
  children: React.ReactNode;
}) {
  const tr = useTranslations();
  const [message, setMessage] = useState("");
  const dialog = useRef<HTMLDialogElement>(null);
  const resolve = useRef<((value: boolean) => void) | null>(null);
  const opener = useRef<HTMLElement | null>(null);
  const finish = (value: boolean) => {
    dialog.current?.close();
    setMessage("");
    resolve.current?.(value);
    resolve.current = null;
    opener.current?.focus();
  };
  useEffect(() => {
    if (message) dialog.current?.showModal();
  }, [message]);
  return (
    <Context.Provider
      value={(text) =>
        new Promise((done) => {
          opener.current = document.activeElement as HTMLElement;
          resolve.current = done;
          setMessage(text);
        })
      }
    >
      {children}
      <dialog
        ref={dialog}
        className="confirmation"
        aria-labelledby="confirmation-title"
        aria-describedby="confirmation-description"
        onCancel={(e) => {
          e.preventDefault();
          finish(false);
        }}
      >
        <h2 id="confirmation-title">{tr("common.confirmTitle")}</h2>
        <p id="confirmation-description">{localizeKnownMessage(message)}</p>
        <div className="actions">
          <button autoFocus className="secondary" onClick={() => finish(false)}>
            {tr("ui.cancel")}
          </button>
          <button className="primary" onClick={() => finish(true)}>
            {tr("common.confirm")}
          </button>
        </div>
      </dialog>
    </Context.Provider>
  );
}
