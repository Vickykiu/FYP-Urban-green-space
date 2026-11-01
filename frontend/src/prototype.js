// Exact labels/order from Figure 4.18; not fabricated database counts or records.
export const CATEGORIES = ['Public park', 'Recreation field', 'Neighbourhood green', 'Community garden'];
export const MAP_ERROR = {
  title: 'Map could not be loaded', subtitle: 'Unable to display the interactive map.',
  message: 'There was a problem loading the map.', guidance: 'Please check the connection and try again.',
};
export function categoryRows(categories) {
  const remaining = [...categories];
  const rows = CATEGORIES.map(name => {
    const index = remaining.findIndex(item => item.category_name === name);
    return index < 0 ? { category_name: name, category_id: null, green_space_count: null } : remaining.splice(index, 1)[0];
  });
  return [...rows, ...remaining];
}
