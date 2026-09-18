# Separate banner workspace implementation

Reference: Infath Marketing and Visual Identity Guide V2, pages 28–33, and the six
supplied physical-auction banner PDF examples. Three layout families: panoramic
(10×3 m, 15×5 m), landscape (4×2 m, 6×3 m, 10×5 m), square (2×2 m). Physical/hybrid
show venue/date/time; electronic shows start/end schedule and platform. Required
content includes official logo, auction and agent identity, contact, licence,
regulatory wording, booklet QR and property facts. Colors/layout are fixed.

- Add a persisted workspace kind and banner configuration to projects; existing
  projects default to booklet. No existing projects or outputs are converted.
- Add a banner navigation section, campaign list/create flow and dedicated steps
  for template, auction details, properties, logos, review, generation and exports.
  Reuse authenticated property/manual/Excel/image services, not the booklet generator.
- Add a template catalogue with source reference previews, banner-specific validation,
  and configuration endpoint. Persist size, enforce banner-only generation in campaigns.
- Render layouts at 1:10 scale PDF with matching aspect ratios and PNG previews;
  document the print scale. Use supplied Infath logo/fonts and real QR codes.
- Keep approval, source-change invalidation and owner isolation. Remove banners from
  the booklet generation selector; retain access to historical banner outputs.
- Test migration defaults, independence from booklet prerequisites, validation,
  property selection/order, rendering dimensions/Arabic, approval/export, user
  isolation, and browser navigation through both workspaces.
