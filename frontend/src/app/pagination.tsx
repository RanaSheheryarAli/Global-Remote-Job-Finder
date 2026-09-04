type PaginationProps = {
  basePath: string;
  page: number;
  pageSize: number;
  total: number;
  query?: Record<string, string | undefined>;
};

function pageHref(
  basePath: string,
  page: number,
  query: Record<string, string | undefined>,
): string {
  const params = new URLSearchParams();
  Object.entries(query).forEach(([key, value]) => {
    if (value) params.set(key, value);
  });
  if (page > 1) params.set("page", String(page));
  const suffix = params.toString();
  return suffix ? `${basePath}?${suffix}` : basePath;
}

function visiblePages(current: number, total: number): Array<number | "ellipsis"> {
  if (total <= 7) return Array.from({ length: total }, (_, index) => index + 1);

  const pages = new Set([1, total, current - 1, current, current + 1]);
  const sorted = [...pages].filter((page) => page >= 1 && page <= total).sort((a, b) => a - b);
  const result: Array<number | "ellipsis"> = [];
  sorted.forEach((page, index) => {
    if (index > 0 && page - sorted[index - 1] > 1) result.push("ellipsis");
    result.push(page);
  });
  return result;
}

export default function Pagination({
  basePath,
  page,
  pageSize,
  total,
  query = {},
}: PaginationProps) {
  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  if (total <= pageSize) return null;

  const currentPage = Math.min(Math.max(page, 1), totalPages);
  const firstResult = (currentPage - 1) * pageSize + 1;
  const lastResult = Math.min(currentPage * pageSize, total);

  return (
    <nav className="pagination" aria-label="Results pages">
      <p>
        Showing <strong>{firstResult}–{lastResult}</strong> of <strong>{total}</strong>
      </p>
      <div className="paginationLinks">
        {currentPage > 1 ? (
          <a href={pageHref(basePath, currentPage - 1, query)} rel="prev">Previous</a>
        ) : (
          <span className="paginationDisabled">Previous</span>
        )}
        {visiblePages(currentPage, totalPages).map((item, index) =>
          item === "ellipsis" ? (
            <span className="paginationEllipsis" key={`ellipsis-${index}`}>…</span>
          ) : (
            <a
              aria-current={item === currentPage ? "page" : undefined}
              className={item === currentPage ? "paginationActive" : ""}
              href={pageHref(basePath, item, query)}
              key={item}
            >
              {item}
            </a>
          ),
        )}
        {currentPage < totalPages ? (
          <a href={pageHref(basePath, currentPage + 1, query)} rel="next">Next</a>
        ) : (
          <span className="paginationDisabled">Next</span>
        )}
      </div>
    </nav>
  );
}
