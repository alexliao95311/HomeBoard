interface FeatureCardProps {
  icon: string;
  title: string;
  description: string;
  phase: string;
}

export function FeatureCard({
  icon,
  title,
  description,
  phase,
}: FeatureCardProps) {
  return (
    <article className="feature-card">
      <div className="feature-card__top">
        <span className="feature-card__icon" aria-hidden="true">
          {icon}
        </span>
        <span className="phase-label">{phase}</span>
      </div>
      <h3>{title}</h3>
      <p>{description}</p>
    </article>
  );
}
