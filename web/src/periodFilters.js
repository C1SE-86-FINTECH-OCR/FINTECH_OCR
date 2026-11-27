import {getQuickDateRange, vietnamDateParts} from './reportDateRanges.js';

export function currentPeriod(now = new Date()) {
  const {year, month} = vietnamDateParts(now);
  const range = getQuickDateRange('month', now);
  return {period: 'month', year, month, date_from: range.from, date_to: range.to};
}

export function shiftPeriod(value, delta) {
  const step = {month: 1, quarter: 3, year: 12}[value.period];
  const index = Number(value.year) * 12 + Number(value.month) - 1 + step * delta;
  return {...value, year: Math.floor(index / 12), month: index % 12 + 1};
}

export function validPeriod(value) {
  if (value.period === 'custom') return Boolean(value.date_from && value.date_to && value.date_from <= value.date_to);
  return value.year >= 1 && value.year <= 9999 && value.month >= 1 && value.month <= 12;
}

export function periodQuery(value) {
  const {period, year, month, date_from, date_to} = value;
  const params = new URLSearchParams({period});
  if (period === 'custom') {
    params.set('date_from', date_from);
    params.set('date_to', date_to);
  } else if (period !== 'all') {
    params.set('year', year);
    if (period === 'month') params.set('month', month);
    if (period === 'quarter') params.set('quarter', Math.ceil(month / 3));
  }
  return params;
}

