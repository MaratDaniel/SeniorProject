// Interface labels, ready for Kazakh (kk) and Russian (ru). No language switch is shown until translations exist.
const LANG="en";
const STR={en:{login:"Log in",join:"Join",saved:"Saved",myBids:"My bids",searchPh:"Search items, auctions, and sellers",allCats:"All categories",upcoming:"Upcoming auctions",how:"How it works",browse:"Browse",auctions:"Auctions",categories:"Categories",legal:"Legal",terms:"Terms (demo placeholder)",privacy:"Privacy (demo placeholder)",footNote:"Demo prototype. All data is illustrative.",viewAll:"View all categories"},kk:{},ru:{}};
const t=k=>(STR[LANG]&&STR[LANG][k])||STR.en[k]||k;
