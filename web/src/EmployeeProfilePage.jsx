import React,{useEffect,useState} from 'react';
import {Link,useParams} from 'react-router-dom';
import {api,roleName} from './api';
export default function EmployeeProfilePage(){
 const {id}=useParams();const [profile,setProfile]=useState(null),[error,setError]=useState('');
 useEffect(()=>{let current=true;setProfile(null);setError('');api('/directory/profiles/'+id).then(value=>{if(current)setProfile(value)}).catch(e=>{if(current)setError(e.message)});return ()=>{current=false}},[id]);
 if(error)return <p className="error" role="alert">{error}</p>;
 if(!profile)return <p>Loading employee profile...</p>;
 return <><header className="pagehead"><div><h1>Employee profile</h1><p>Team member information and completed-trip statistics</p></div></header><section className="panel employee-profile-card"><div className="employee-profile-heading"><span className="avatar">{profile.full_name.split(/\s+/).filter(Boolean).slice(-2).map(x=>x[0]).join('')}</span><div><h2>{profile.full_name}</h2><span className="pill">{roleName(profile.role)}</span></div></div>{profile.email&&<p><strong>Email: </strong>{profile.email}</p>}{profile.status&&<p><strong>Account status: </strong>{profile.status==='active'?'Active':'Deactivated'}</p>}<div className="employee-profile-stats"><div><small>Completed trips · All time</small><strong>{profile.completed_trips}</strong></div><div><small>Team ranking · All time</small><strong>{profile.rank?'#'+profile.rank:'Not ranked'}</strong></div></div><Link className="btn btn-primary" to={'/ranking?period=all#ranking-'+profile.id}>View in Ranking</Link></section></>;
}
