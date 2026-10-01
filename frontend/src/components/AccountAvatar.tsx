"use client";

import { useEffect, useRef, useState } from "react";
import Image from "next/image";
import { API_BASE, apiFetch } from "@/lib/api";
import type { CachedUser } from "@/lib/auth-storage";

type Props = {
  user: CachedUser;
  onChange: (user: CachedUser) => void;
};

const MAX_FILE_SIZE = 5 * 1024 * 1024;
const MAX_AVATAR_SIZE = 512 * 1024;
const IMAGE_TYPES = new Set(["image/jpeg", "image/png", "image/webp"]);

async function prepareAvatar(file: File): Promise<string> {
  if (!IMAGE_TYPES.has(file.type)) throw new Error("Chỉ hỗ trợ ảnh JPG, PNG hoặc WebP.");
  if (file.size > MAX_FILE_SIZE) throw new Error("Ảnh gốc phải nhỏ hơn 5 MB.");

  const bitmap = await createImageBitmap(file);
  try {
    const scale = Math.min(1, 256 / Math.max(bitmap.width, bitmap.height));
    const canvas = document.createElement("canvas");
    canvas.width = Math.max(1, Math.round(bitmap.width * scale));
    canvas.height = Math.max(1, Math.round(bitmap.height * scale));
    const context = canvas.getContext("2d");
    if (!context) throw new Error("Không thể xử lý ảnh này.");
    context.fillStyle = "#ffffff";
    context.fillRect(0, 0, canvas.width, canvas.height);
    context.drawImage(bitmap, 0, 0, canvas.width, canvas.height);
    const dataUrl = canvas.toDataURL("image/jpeg", 0.85);
    if (Math.ceil((dataUrl.length - "data:image/jpeg;base64,".length) * 3 / 4) > MAX_AVATAR_SIZE) {
      throw new Error("Ảnh sau xử lý vẫn quá lớn. Vui lòng chọn ảnh khác.");
    }
    return dataUrl;
  } finally {
    bitmap.close();
  }
}

export default function AccountAvatar({ user, onChange }: Props) {
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const menuRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const avatar = typeof user.avatar_data_url === "string" && user.avatar_data_url.startsWith("data:image/jpeg;base64,")
    ? user.avatar_data_url
    : null;

  useEffect(() => {
    if (!open) return;
    const onPointerDown = (event: PointerEvent) => {
      if (!menuRef.current?.contains(event.target as Node)) setOpen(false);
    };
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false);
    };
    document.addEventListener("pointerdown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("pointerdown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [open]);

  const chooseFile = async (file?: File) => {
    if (!file) return;
    setBusy(true);
    setError(null);
    try {
      const dataUrl = await prepareAvatar(file);
      const result = await apiFetch<{ avatar_data_url: string }>(`${API_BASE}/auth/avatar`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ data_url: dataUrl }),
      });
      const nextUser = { ...user, avatar_data_url: result.avatar_data_url };
      localStorage.setItem("user_cache", JSON.stringify(nextUser));
      onChange(nextUser);
      setOpen(false);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Không thể đổi ảnh đại diện.");
    } finally {
      setBusy(false);
      if (inputRef.current) inputRef.current.value = "";
    }
  };

  const removeAvatar = async () => {
    setBusy(true);
    setError(null);
    try {
      await apiFetch(`${API_BASE}/auth/avatar`, { method: "DELETE" });
      const nextUser = { ...user, avatar_data_url: null };
      localStorage.setItem("user_cache", JSON.stringify(nextUser));
      onChange(nextUser);
      setOpen(false);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Không thể xóa ảnh đại diện.");
    } finally {
      setBusy(false);
    }
  };

  return <div className="account-avatar-wrapper" ref={menuRef}>
    <button type="button" className="account-avatar-button" aria-label="Thay ảnh đại diện" aria-expanded={open} aria-haspopup="menu" onClick={() => { setOpen(!open); setError(null); }}>
      {avatar ? <Image src={avatar} alt="" width={32} height={32} unoptimized /> : user.email.charAt(0).toUpperCase()}
    </button>
    {open && <div className="account-avatar-menu" role="menu">
      <div className="account-avatar-email">{user.email}</div>
      <button type="button" role="menuitem" disabled={busy} onClick={() => inputRef.current?.click()}>Tải ảnh đại diện lên</button>
      {avatar && <button type="button" role="menuitem" disabled={busy} onClick={removeAvatar}>Xóa ảnh đại diện</button>}
      {busy && <div className="account-avatar-status" role="status">Đang lưu ảnh…</div>}
      {error && <div className="account-avatar-error" role="alert">{error}</div>}
    </div>}
    <input ref={inputRef} type="file" accept="image/jpeg,image/png,image/webp" aria-label="Chọn ảnh đại diện" className="account-avatar-input" onChange={(event) => { void chooseFile(event.target.files?.[0]); }} />
  </div>;
}
