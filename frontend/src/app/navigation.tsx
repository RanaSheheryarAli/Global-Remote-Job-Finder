"use client";

import { usePathname } from "next/navigation";

const links = [
  { href: "/matches", label: "Matches" },
  { href: "/jobs", label: "All jobs" },
  { href: "/profile", label: "My profile" },
  { href: "/sources", label: "Sources" },
];

export default function Navigation() {
  const pathname = usePathname();

  return (
    <header className="siteHeader">
      <nav className="siteNav" aria-label="Main navigation">
        <a className="siteBrand" href="/matches">
          <span aria-hidden="true">GR</span>
          <strong>Remote Job Finder</strong>
        </a>
        <div className="siteNavLinks">
          {links.map((link) => {
            const active = pathname === link.href || pathname.startsWith(`${link.href}/`);
            return (
              <a
                className={active ? "siteNavActive" : ""}
                href={link.href}
                key={link.href}
                aria-current={active ? "page" : undefined}
              >
                {link.label}
              </a>
            );
          })}
        </div>
      </nav>
    </header>
  );
}
