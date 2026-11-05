import Link from "next/link";

export function Logo() {
  return (
    <Link href="/" className="brand" aria-label="NetAccess Systems Nigeria home">
      <img src="/netaccess-logo.svg" alt="NetAccess Systems Nigeria" />
    </Link>
  );
}
