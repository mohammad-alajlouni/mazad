"use client";
import { useTranslations } from "next-intl";
import { Sparkles, Zap } from "lucide-react";
import { api, send, Detail, Item, Run } from "./api";
import { useConfirm } from "./Confirmation";

const pick = <T,>(list: readonly T[]) =>
  list[Math.floor(Math.random() * list.length)];
const between = (low: number, high: number) =>
  Math.floor(low + Math.random() * (high - low + 1));
const digits = (count: number) =>
  String(between(1, 9)) +
  Array.from({ length: count - 1 }, () => between(0, 9)).join("");

const PLACES = [
  ["الرياض", ["الصحافة", "الملقا", "النخيل", "النرجس", "العليا"]],
  ["جدة", ["الشاطئ", "الروضة", "الأندلس", "النعيم"]],
  ["الدمام", ["الفيصلية", "الشاطئ", "المزروعية"]],
  ["أبها", ["المنسك", "الخالدية", "اليمانية"]],
] as const;
const KINDS = [
  ["أرض تجارية", "تجاري"],
  ["فيلا سكنية", "سكني"],
  ["عمارة استثمارية", "تجاري"],
  ["أرض سكنية", "سكني"],
  ["مجمع تجاري", "تجاري"],
] as const;

function isoDay(offset: number) {
  const day = new Date(Date.now() + offset * 86400000);
  return day.toISOString().slice(0, 10);
}

// A plain picture standing in for a property photograph (drawn in the browser).
async function picture(label: string, hue: number) {
  const canvas = document.createElement("canvas");
  canvas.width = 1600;
  canvas.height = 1000;
  const c = canvas.getContext("2d")!;
  const sky = c.createLinearGradient(0, 0, 0, 1000);
  sky.addColorStop(0, `hsl(${hue} 55% 72%)`);
  sky.addColorStop(1, `hsl(${hue + 25} 45% 88%)`);
  c.fillStyle = sky;
  c.fillRect(0, 0, 1600, 1000);
  c.fillStyle = `hsl(${hue + 90} 22% 46%)`;
  c.fillRect(0, 700, 1600, 300);
  for (let n = 0; n < 5; n++) {
    const width = between(170, 300);
    const height = between(220, 520);
    const left = 90 + n * 300;
    c.fillStyle = `hsl(${hue + 180} 18% ${between(30, 55)}%)`;
    c.fillRect(left, 720 - height, width, height);
    c.fillStyle = "#ffffff66";
    for (let y = 740 - height; y < 680; y += 60)
      for (let x = left + 22; x < left + width - 40; x += 58)
        c.fillRect(x, y, 30, 34);
  }
  c.fillStyle = "#ffffffcc";
  c.font = "bold 46px sans-serif";
  c.textAlign = "center";
  c.fillText(label, 800, 920);
  return new Promise<Blob>((resolve) =>
    canvas.toBlob((blob) => resolve(blob!), "image/jpeg", 0.88),
  );
}

// One click fills a whole project with random sample data, so the outputs can
// be generated and looked at. It only uses the forms' own saving requests.
export default function SampleFill({
  detail,
  run,
  reload,
  onFilled,
}: {
  detail: Detail;
  run: Run;
  reload: () => Promise<void>;
  // Open forms hold the old values: the caller shows them afresh.
  onFilled?: () => void;
}) {
  const t = useTranslations("sample");
  const confirm = useConfirm();
  const fill = async () => {
    if (!(await confirm(t("confirm")))) return;
    await run(async () => {
      const project = detail.project;
      const [city, districts] = pick(PLACES);
      const kind = pick(["electronic", "physical", "hybrid"] as const);
      const start = between(20, 60);
      const name =
        "مزاد " + pick(["أعيان", "واحة", "درة", "آفاق", "روابي"]) + " " + city;
      const auction = {
        ...project.auction,
        auction_name: name,
        auction_type: kind,
        auction_date: isoDay(start),
        auction_start_date: isoDay(start),
        auction_end_date: isoDay(start + between(1, 3)),
        start_time: pick(["10:00", "16:00", "16:30"]),
        end_time: pick(["20:00", "21:00", "22:00"]),
        physical_location: `قاعة المزادات - ${city}`,
        electronic_platform_name: "منصة السعودية للمزادات",
        electronic_platform_url: "https://example.com/platform",
        auction_location_url: "https://example.com/hall",
        booklet_url: "https://example.com/booklet",
        contact_url: "https://example.com/contact",
        license_number: digits(9),
        supervising_authority: "مركز الإسناد والتصفية (إنفاذ)",
        auction_contact_number: "05" + digits(8),
        legal_announcement_text:
          "تعلن الشركة عن البيع بالمزاد العلني\nوبإشراف مركز الإسناد والتصفية «إنفاذ»",
        court_decision_text: "وبقرار من محكمة التنفيذ",
        selected_cover_template_id:
          project.auction?.selected_cover_template_id ||
          "infath-" + between(1, 6),
        document_language: project.auction?.document_language || "ar",
      };
      await api(`/projects/${project.id}`, {
        method: "PUT",
        // A project still called after its auction follows the new name.
        body: send({
          ...project,
          name:
            !project.auction?.auction_name ||
            project.name === project.auction.auction_name
              ? name
              : project.name,
          auction,
        }),
      });
      let items: Item[] = detail.items;
      if (!items.length) {
        items = [];
        for (let n = 0; n < 3; n++) {
          const [type, usage] = pick(KINDS);
          const district = pick(districts);
          items.push(
            await api<Item>(`/projects/${project.id}/items`, {
              method: "POST",
              body: send({
                title: `${type} · ${district}`,
                description: `${type} في حي ${district} بمدينة ${city}، على شارعين وقريبة من الخدمات والطرق الرئيسية.`,
                property_data: {
                  property_type: type,
                  city,
                  district,
                  usage,
                  area: String(between(400, 2500)),
                  deed_number: digits(12),
                  plan_number: digits(4),
                  plot_number: String(between(1, 900)),
                  execution_request_number: digits(10),
                  participation_amount: String(between(2, 15) * 5000),
                  ...(kind === "physical"
                    ? {}
                    : {
                        auction_close_date: auction.auction_end_date,
                        auction_close_time: `${18 + n}:00`,
                      }),
                  features: [
                    "موقع مميز قريب من الطريق الرئيسي",
                    "جميع الخدمات متوفرة",
                  ],
                  boundaries: {
                    north_description: `شارع عرض ${between(15, 40)}م`,
                    south_description: `قطعة رقم ${between(1, 900)}`,
                    east_description: `قطعة رقم ${between(1, 900)}`,
                    west_description: `شارع عرض ${between(10, 30)}م`,
                    north_length: `${between(20, 60)}م`,
                    south_length: `${between(20, 60)}م`,
                    east_length: `${between(20, 60)}م`,
                    west_length: `${between(20, 60)}م`,
                  },
                },
              }),
            }),
          );
        }
      }
      // Every property needs its main photograph before generating.
      for (const [n, item] of items.entries()) {
        if (
          detail.images.some(
            (i) => i.item_id === item.id && i.category === "main",
          )
        )
          continue;
        const body = new FormData();
        body.set("category", "main");
        body.set("item_id", item.id);
        body.set(
          "file",
          await picture(t("photo", { title: item.title }), 190 + n * 40),
          `sample-${n + 1}.jpg`,
        );
        await api(`/projects/${project.id}/images`, { method: "POST", body });
      }
      await reload();
      onFilled?.();
    }, t("done"));
  };
  return (
    <div className="sample-fill">
      <span>
        <Sparkles size={18} />
        {t("prompt")}
      </span>
      <button
        type="button"
        className="sample-button"
        onClick={() => void fill()}
      >
        <Zap size={15} />
        {t("action")}
      </button>
    </div>
  );
}
