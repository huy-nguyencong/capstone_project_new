import { useId } from 'react'
import { cx } from './cx'

export function Field({ label, className, children, htmlFor }) {
  return (
    <div className={cx('field', className)}>
      <label htmlFor={htmlFor}>{label}</label>
      {children}
    </div>
  )
}

export function Input({ className, ...props }) {
  return <input className={cx('input', className)} {...props} />
}

export function Textarea({ className, ...props }) {
  return <textarea className={cx('input', className)} {...props} />
}

export function Select({ options, placeholder, className, ...props }) {
  return (
    <select className={cx('input', className)} {...props}>
      {placeholder != null && <option value="">{placeholder}</option>}
      {options.map((o) => (
        <option key={o.value} value={o.value}>
          {o.label}
        </option>
      ))}
    </select>
  )
}

export function TextField({ label, className, ...props }) {
  const id = useId()
  return (
    <Field label={label} className={className} htmlFor={id}>
      <Input id={id} {...props} />
    </Field>
  )
}

export function TextAreaField({ label, className, ...props }) {
  const id = useId()
  return (
    <Field label={label} className={className} htmlFor={id}>
      <Textarea id={id} {...props} />
    </Field>
  )
}

export function SelectField({ label, className, ...props }) {
  const id = useId()
  return (
    <Field label={label} className={className} htmlFor={id}>
      <Select id={id} {...props} />
    </Field>
  )
}
