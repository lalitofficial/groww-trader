import type { Catalyst } from "@/lib/types";

export function CatalystTimeline({ catalysts }: { catalysts: Catalyst[] }) {
  return (
    <section className="panel">
      <div className="panel-header">
        <strong>Catalysts</strong>
        <span className="muted">{catalysts.length} sources</span>
      </div>
      <div className="panel-body">
        {catalysts.length === 0 ? <div className="muted">No catalyst sources found yet.</div> : null}
        {catalysts.map((item) => (
          <article className="catalyst" key={item.url}>
            <a href={item.url} target="_blank" rel="noreferrer">
              <strong>{item.title}</strong>
            </a>
            <div className="muted">
              {item.source_type} · {item.published_at || "undated"} · relevance {item.relevance_score ?? "-"}
            </div>
            {item.summary ? <p>{item.summary}</p> : null}
          </article>
        ))}
      </div>
    </section>
  );
}
