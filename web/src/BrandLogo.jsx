import React from 'react';
import mark from './assets/fintech-logo.svg';
import './brandLogo.css';

export function BrandMark() {
  return <img className="fintech-mark" src={mark} alt="" aria-hidden="true"/>;
}

export default function BrandLogo() {
  return <><BrandMark/><span className="fintech-wordmark">FINTECH<strong>OCR / WORKSPACE</strong></span></>;
}
