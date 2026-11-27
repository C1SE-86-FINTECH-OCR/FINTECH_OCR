import test from 'node:test';
import assert from 'node:assert/strict';
import {currentPeriod, periodQuery, shiftPeriod, validPeriod} from '../src/periodFilters.js';

test('ranking defaults to the Vietnam month across the UTC calendar boundary', () => {
  const period = currentPeriod(new Date('2026-10-31T17:00:00Z'));
  assert.equal(periodQuery(period).toString(), 'period=month&year=2026&month=11');
  assert.equal(periodQuery({...period, period:'quarter'}).get('quarter'), '4');
  assert.equal(periodQuery({...period, period:'year'}).toString(), 'period=year&year=2026');
});

test('ranking steps months, quarters and years across calendar boundaries', () => {
  const current = {year:2026, month:12, period:'month'};
  assert.deepEqual(shiftPeriod(current,1), {year:2027, month:1, period:'month'});
  const quarter = shiftPeriod({...current, period:'quarter'},1);
  assert.equal(periodQuery(quarter).toString(), 'period=quarter&year=2027&quarter=1');
  assert.equal(shiftPeriod({...current, period:'year'},-1).year, 2025);
  assert.equal(validPeriod({period:'custom', date_from:'2026-12-31', date_to:'2026-12-01'}),false);
});
