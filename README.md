# Ramon's Social Publishing Engine

**[AI Mastermind](https://growth-and-wealth-ai.ca/?src=github)** (free, Level 1) · **[Superstars Multiplier](https://growth-and-wealth-superstars.ca/?src=github)** · **[Level 2 · AI Platform](https://growth-and-wealth-superstars.ca/automation.html?src=github)** · **[Free Claude skills for agents](https://github.com/ramongtzl/superstars-real-estate-skills)** · [Español](#en-español)

This is the engine behind **Ramon Gutierrez's** social media. It runs on autopilot: GitHub Actions publish each scheduled post, and GitHub Pages hosts the images and reels that the platforms pull in. Every morning it also collects how each post performed.

It is a live example of what we build in the **AI Mastermind** and set up for you in **Level 2**: AI drafts, you approve, and the system publishes on schedule.

## What it does

| Part | What it does |
|---|---|
| `schedule.csv` + `post.yml` | The content calendar. Each row goes out at its time to Instagram, Facebook, YouTube, Threads and LinkedIn, in English and Spanish. |
| `assets/` | Images, carousels and reels, served by GitHub Pages so each platform can fetch them. |
| `stats.yml` | A daily job that measures followers and each post's likes and comments. The results are stored encrypted. |
| `stats_report.py` | Turns those numbers into a weekly report: top posts, best series, best hour, English vs Spanish. |
| `maintain.yml` | Keeps the rolling calendar and the reels window current. |

Access keys live in GitHub Secrets, never in this code. Stats are encrypted before they are saved.

## Want this for your business?

1. **Start free:** the [AI Mastermind](https://growth-and-wealth-ai.ca/?src=github) runs 4 weeks, bilingual, and is open to agents at any brokerage.
2. **Have it built for you:** in [Level 2 · AI Platform](https://growth-and-wealth-superstars.ca/automation.html?src=github), Ramon sets up routines, content in your voice and scheduled publishing in your own accounts.
3. **Grow as a leader:** [Superstars Multiplier](https://growth-and-wealth-superstars.ca/?src=github).

---

## En español

**[AI Mastermind](https://growth-and-wealth-ai.ca/es/?src=github)** (gratis, Nivel 1) · **[Superstars Multiplier](https://growth-and-wealth-superstars.ca/es/?src=github)** · **[Nivel 2 · Plataforma IA](https://growth-and-wealth-superstars.ca/es/automation.html?src=github)**

Este es el motor de las redes sociales de **Ramon Gutierrez**. GitHub Actions publica cada post a su hora en Instagram, Facebook, YouTube, Threads y LinkedIn, en inglés y en español. GitHub Pages sirve las imágenes y los reels. Cada mañana mide cómo le fue a cada post, y cada lunes llega un reporte.

Es un ejemplo en vivo de lo que construimos en el **AI Mastermind** (gratis, 4 semanas) y de lo que armamos contigo en el **Nivel 2**: la IA redacta, tú apruebas y el sistema publica.

---

Ramon Gutierrez is a REALTOR&reg; with eXp Realty of Canada. The AI Mastermind, Superstars Multiplier and the AI Platform are Ramon's own programs, not eXp Realty programs or services. No income claims.
