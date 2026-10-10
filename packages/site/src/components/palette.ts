/** Categorical series colors, checked for contrast against the near-black background. */
export const SERIES = ['#ff5a1a', '#ececea', '#ffb020', '#4fc3f7', '#7bd88f', '#d98be0', '#f2777a', '#a8a29e'];
export const seriesColor = (i: number) => SERIES[i % SERIES.length]!;
