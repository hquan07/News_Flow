"use client";

import React, { useEffect, useRef, useCallback } from "react";
import { X } from "lucide-react";

interface ModalProps {
  open: boolean;
  onClose: () => void;
  title?: React.ReactNode;
  children: React.ReactNode;
  footer?: React.ReactNode;
  ariaLabelledBy?: string;
  className?: string;
}

export default function Modal({
  open,
  onClose,
  title,
  children,
  footer,
  ariaLabelledBy,
  className,
}: ModalProps) {
  const overlayRef = useRef<HTMLDivElement>(null);
  const closeBtnRef = useRef<HTMLButtonElement>(null);
  const contentRef = useRef<HTMLDivElement>(null);

  // Focus trap & initial focus
  useEffect(() => {
    if (!open) return;

    // Focus the close button on open
    closeBtnRef.current?.focus();

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        onClose();
        return;
      }

      // Focus trap
      if (e.key === "Tab" && contentRef.current) {
        const focusable = contentRef.current.querySelectorAll<HTMLElement>(
          'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
        );
        if (focusable.length === 0) return;
        const first = focusable[0];
        const last = focusable[focusable.length - 1];

        if (e.shiftKey) {
          if (document.activeElement === first) {
            e.preventDefault();
            last.focus();
          }
        } else {
          if (document.activeElement === last) {
            e.preventDefault();
            first.focus();
          }
        }
      }
    };

    document.addEventListener("keydown", handleKeyDown);
    document.body.style.overflow = "hidden";

    return () => {
      document.removeEventListener("keydown", handleKeyDown);
      document.body.style.overflow = "";
    };
  }, [open, onClose]);

  const handleBackdropClick = useCallback(
    (e: React.MouseEvent) => {
      if (e.target === overlayRef.current) {
        onClose();
      }
    },
    [onClose]
  );

  if (!open) return null;

  return (
    <div
      ref={overlayRef}
      className={`modal-overlay ${className || ""}`}
      onClick={handleBackdropClick}
      role="presentation"
    >
      <div
        ref={contentRef}
        className="modal-container"
        role="dialog"
        aria-modal="true"
        aria-labelledby={ariaLabelledBy}
      >
        {title && (
          <div className="modal-header">
            <div className="modal-title" id={ariaLabelledBy}>
              {title}
            </div>
            <button
              ref={closeBtnRef}
              className="modal-close-btn"
              onClick={onClose}
              aria-label="Close dialog"
              type="button"
            >
              <X size={20} />
            </button>
          </div>
        )}

        <div className="modal-body">{children}</div>

        {footer && <div className="modal-footer">{footer}</div>}
      </div>
    </div>
  );
}
