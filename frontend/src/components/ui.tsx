import * as Dialog from '@radix-ui/react-dialog';
import { X, ArrowRight, FileText, CheckCircle2, AlertCircle } from 'lucide-react';
import { Link } from 'react-router-dom';
import {
  cloneElement,
  isValidElement,
  useId,
  useRef,
  type ButtonHTMLAttributes,
  type ReactNode,
} from 'react';
export function Button({
  children,
  variant = 'primary',
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: 'primary' | 'secondary' | 'danger' }) {
  return (
    <button {...props} className={'button ' + variant + ' ' + (props.className ?? '')}>
      {children}
    </button>
  );
}
export function LinkButton({
  to,
  children,
  secondary = false,
}: {
  to: string;
  children: ReactNode;
  secondary?: boolean;
}) {
  return (
    <Link className={'button ' + (secondary ? 'secondary' : 'primary')} to={to}>
      {children}
      <ArrowRight size={16} />
    </Link>
  );
}
export function Card({ children, className = '' }: { children: ReactNode; className?: string }) {
  return <section className={'card ' + className}>{children}</section>;
}
export function Heading({
  eyebrow,
  title,
  children,
  actions,
  level = 1,
}: {
  eyebrow?: string;
  title: string;
  children?: ReactNode;
  actions?: ReactNode;
  level?: 1 | 2;
}) {
  const Title = level === 1 ? 'h1' : 'h2';
  return (
    <div className="page-heading">
      <div>
        {eyebrow && <p className="eyebrow">{eyebrow}</p>}
        <Title>{title}</Title>
        {children && <p className="muted">{children}</p>}
      </div>
      {actions && <div className="actions">{actions}</div>}
    </div>
  );
}
export function Notice({
  children,
  tone = 'info',
}: {
  children: ReactNode;
  tone?: 'info' | 'warning' | 'success';
}) {
  return (
    <div className={'notice ' + tone}>
      {tone === 'success' ? <CheckCircle2 size={19} /> : <AlertCircle size={19} />}
      <div>{children}</div>
    </div>
  );
}
export function Field({
  label,
  children,
  hint,
}: {
  label: string;
  children: ReactNode;
  hint?: string;
}) {
  const id = useId();
  return (
    <div className="field">
      <label htmlFor={id}>{label}</label>
      {isValidElement<{ id?: string; 'aria-describedby'?: string }>(children)
        ? cloneElement(children, { id, 'aria-describedby': hint ? id + '-hint' : undefined })
        : children}
      {hint && <small id={id + '-hint'}>{hint}</small>}
    </div>
  );
}
export function Check({
  children,
  ...props
}: ButtonHTMLAttributes<HTMLInputElement> & { checked?: boolean; onChange?: () => void }) {
  return (
    <label className="check">
      <input type="checkbox" {...props} />
      <span>{children}</span>
    </label>
  );
}
export function Modal({
  open,
  onOpenChange,
  title,
  description,
  children,
}: {
  open: boolean;
  onOpenChange: (value: boolean) => void;
  title: string;
  description: string;
  children: ReactNode;
}) {
  const opener = useRef<HTMLElement | null>(null);
  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="overlay" />
        <Dialog.Content
          className="modal"
          onOpenAutoFocus={() => {
            opener.current =
              document.activeElement instanceof HTMLElement ? document.activeElement : null;
          }}
          onCloseAutoFocus={(e) => {
            e.preventDefault();
            opener.current?.focus();
          }}
        >
          <div className="modal-head">
            <Dialog.Title>{title}</Dialog.Title>
            <Dialog.Close aria-label="Close dialog" className="icon-button">
              <X size={20} />
            </Dialog.Close>
          </div>
          <Dialog.Description className="muted">{description}</Dialog.Description>
          {children}
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
export function Empty({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="empty">
      <FileText size={32} />
      <h2>{title}</h2>
      {children}
    </div>
  );
}
export function Badge({ children, tone = 'neutral' }: { children: ReactNode; tone?: string }) {
  return <span className={'badge ' + tone}>{children}</span>;
}
