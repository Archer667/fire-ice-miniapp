export const PERSONAL_PAGES = [3,4,9,10,11,12,13,14,15,16,17,18];
export const canOpenPage = (me, page) => !me?.landless || PERSONAL_PAGES.includes(page);
