import { theme } from './theme.js';
// One palette shared by the 2D map, 3D robots, route lines and status cards.
const palette=theme.robots;
export const robotColor=id=>palette[(id-1)%palette.length];
